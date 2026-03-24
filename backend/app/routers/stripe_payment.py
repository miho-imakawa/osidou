import csv
import io
import os
from datetime import datetime, timedelta, date, timezone
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from calendar import monthrange

from ..database import get_db

router = APIRouter(prefix="/api", tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://osidou-o4gz.vercel.app")

PRICE_FEELING_LOG    = 200
PRICE_FRIENDS_LOG    = 1000
PRICE_MEETUP         = 500
PRICE_AFFILIATE_NONE = 200
PRICE_PER_FRIEND     = 100   # 11人目以降1人あたり月100円
FRIEND_FREE_LIMIT    = 10   # 無料枠 


# ===============================================================
# FRIEND's MANAGER ユーティリティ
# ===============================================================

def _get_or_create_stripe_customer(user_id: int, db: Session) -> str:
    """
    users テーブルから email を取得し、Stripe Customer を作成 or 取得する。
    stripe_customer_id は friend_manager_subscriptions に保存。
    """
    row = db.execute(
        text("SELECT id, email, nickname FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    # 既存の customer_id を確認
    sub_row = db.execute(
        text("SELECT stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()

    if sub_row and sub_row.stripe_customer_id:
        return sub_row.stripe_customer_id

    # 新規作成
    customer = stripe.Customer.create(
        email=row.email,
        name=row.nickname or f"user_{user_id}",
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def _calc_amount(friend_count: int) -> int:
    """友達数から月額を計算する。無料枠以下は0円。"""
    extra = max(0, friend_count - FRIEND_FREE_LIMIT)
    return extra * PRICE_PER_FRIEND


def _get_friend_count(user_id: int, db: Session) -> int:
    """現在の友達数を取得する。Friendshipモデルに status カラムはないので user_id のみで集計。"""
    result = db.execute(text("""
        SELECT COUNT(*) AS cnt FROM friendships
        WHERE user_id = :uid
    """), {"uid": user_id}).fetchone()
    return result.cnt if result else 0


def _create_subscription_for_requester(requester_id: int, db: Session) -> dict:
    """
    承認時に呼び出す共通関数。
    申請者のカード（Setup済み）でサブスクを作成、または既存サブスクの金額を更新する。
    カード未登録の場合は何もしない（無料枠内とみなす）。
    """
    friend_count = _get_friend_count(requester_id, db)
    # 承認後の人数（+1）で計算
    new_count = friend_count + 1
    extra = max(0, new_count - FRIEND_FREE_LIMIT)

    if extra <= 0:
        return {"requires_payment": False}

    amount = extra * PRICE_PER_FRIEND

    sub_row = db.execute(
        text("""
            SELECT stripe_customer_id, stripe_subscription_id, status
            FROM friend_manager_subscriptions
            WHERE user_id = :uid
        """),
        {"uid": requester_id}
    ).fetchone()

    # カード未登録（SetupIntentをスキップした場合）→ 何もしない
    if not sub_row or not sub_row.stripe_customer_id:
        return {"requires_payment": False, "skipped": True}

    customer_id = sub_row.stripe_customer_id

    # ── 既存アクティブサブスクがある → 金額更新のみ ──
    if sub_row.stripe_subscription_id and sub_row.status == "active":
        subscription = stripe.Subscription.retrieve(sub_row.stripe_subscription_id)
        item_id = subscription["items"]["data"][0]["id"]
        new_price = stripe.Price.create(
            unit_amount=amount,
            currency="jpy",
            recurring={"interval": "month"},
            product_data={"name": "FRIEND's manager"},
            metadata={"user_id": str(requester_id), "extra_count": str(extra)},
        )
        stripe.Subscription.modify(
            sub_row.stripe_subscription_id,
            items=[{"id": item_id, "price": new_price.id}],
            proration_behavior="none",
        )
        db.execute(text("""
            UPDATE friend_manager_subscriptions
            SET friend_count = :fc,
                charged_extra_count = :ec,
                current_amount = :amt,
                updated_at = NOW()
            WHERE user_id = :uid
        """), {"fc": new_count, "ec": extra, "amt": amount, "uid": requester_id})
        db.commit()
        return {"updated": True, "monthly_amount": amount}

    # ── 新規サブスク作成 ──
    # Setup済みのカードを取得（最新のもの）
    payment_methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
    if not payment_methods.data:
        # カードが見つからない（SetupIntentが未完了など）→ スキップ
        return {"requires_payment": False, "skipped": True, "reason": "no_payment_method"}

    pm_id = payment_methods.data[0].id

    # デフォルトPMを設定
    stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": pm_id})

    # 月末7日ルールで課金開始日を決定
    today = datetime.now(timezone.utc).date()
    _, last_day = monthrange(today.year, today.month)
    days_until_end = last_day - today.day

    price = stripe.Price.create(
        unit_amount=amount,
        currency="jpy",
        recurring={"interval": "month"},
        product_data={"name": "FRIEND's manager"},
        metadata={"user_id": str(requester_id), "extra_count": str(extra)},
    )

    sub_params: dict = {
        "customer": customer_id,
        "items": [{"price": price.id}],
        "default_payment_method": pm_id,
        "metadata": {
            "user_id": str(requester_id),
            "product": "friend_manager",
            "extra_count": str(extra),
            "friend_count": str(new_count),
        },
    }

    if days_until_end < 7:
        # 翌月1日から課金開始（trial期間を設定）
        if today.month == 12:
            billing_start = date(today.year + 1, 1, 1)
        else:
            billing_start = date(today.year, today.month + 1, 1)
        trial_end = int(
            datetime(billing_start.year, billing_start.month, 1, tzinfo=timezone.utc).timestamp()
        )
        sub_params["trial_end"] = trial_end

    subscription = stripe.Subscription.create(**sub_params)

    db.execute(text("""
        UPDATE friend_manager_subscriptions
        SET stripe_subscription_id = :sid,
            status = 'active',
            friend_count = :fc,
            charged_extra_count = :ec,
            current_amount = :amt,
            updated_at = NOW()
        WHERE user_id = :uid
    """), {
        "sid": subscription.id,
        "fc": new_count,
        "ec": extra,
        "amt": amount,
        "uid": requester_id,
    })
    db.commit()

    return {"subscribed": True, "monthly_amount": amount, "extra_count": extra}


# ===============================================================
# FRIEND's MANAGER エンドポイント
# ===============================================================

# -------------------------------------------------------
# FM-0. SetupIntent 作成（申請者が人数超過時）
#        カード登録のみ。まだ課金しない。
# -------------------------------------------------------
@router.post("/stripe/friend-manager-setup-intent")
async def create_friend_manager_setup_intent(data: dict, db: Session = Depends(get_db)):
    """
    申請者が FRIEND_FREE_LIMIT 人以上のフレンドを持つ場合に呼び出す。
    Stripe Checkout（mode=setup）でカードを登録させる。
    課金は承認者が承認したタイミングで開始する。
    """
    requester_id = data.get("requesterId")
    receiver_id  = data.get("receiverId")
    if not requester_id or not receiver_id:
        raise HTTPException(status_code=400, detail="requesterId と receiverId が必要です")

    requester_id = int(requester_id)
    receiver_id  = int(receiver_id)

    # Stripe Customer を作成 or 取得
    customer_id = _get_or_create_stripe_customer(requester_id, db)

    # customer_id を friend_manager_subscriptions に保存（初回のみ INSERT）
    existing = db.execute(
        text("SELECT id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": requester_id}
    ).fetchone()

    if not existing:
        db.execute(text("""
            INSERT INTO friend_manager_subscriptions
                (user_id, stripe_customer_id, status, friend_count, charged_extra_count, current_amount)
            VALUES (:uid, :cid, 'pending', 0, 0, 0)
        """), {"uid": requester_id, "cid": customer_id})
    else:
        db.execute(text("""
            UPDATE friend_manager_subscriptions
            SET stripe_customer_id = :cid
            WHERE user_id = :uid
        """), {"uid": requester_id, "cid": customer_id})
    db.commit()

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            mode="setup",
            success_url=(
                f"{FRONTEND_URL}/friends"
                f"?fm_setup_done=true"
                f"&receiver_id={receiver_id}"
                f"&setup_session_id={{CHECKOUT_SESSION_ID}}"
            ),
            cancel_url=f"{FRONTEND_URL}/friends",
            metadata={
                "user_id":     str(requester_id),
                "receiver_id": str(receiver_id),
                "product":     "friend_manager_setup",
            },
        )
        return {"checkout_url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# FM-1. サブスクリプション状態チェック
# -------------------------------------------------------
@router.get("/stripe/friend-manager-status")
async def get_friend_manager_status(user_id: int, db: Session = Depends(get_db)):
    friend_count = _get_friend_count(user_id, db)
    amount = _calc_amount(friend_count)

    sub = db.execute(
        text("""
            SELECT stripe_subscription_id, status, current_amount, charged_extra_count
            FROM friend_manager_subscriptions
            WHERE user_id = :uid
        """),
        {"uid": user_id}
    ).fetchone()

    return {
        "friend_count":   friend_count,
        "free_limit":     FRIEND_FREE_LIMIT,
        "extra_count":    max(0, friend_count - FRIEND_FREE_LIMIT),
        "monthly_amount": amount,
        "subscription": {
            "exists":          sub is not None,
            "status":          sub.status if sub else "none",
            "subscription_id": sub.stripe_subscription_id if sub else None,
            "current_amount":  sub.current_amount if sub else 0,
        } if sub else {"exists": False, "status": "none"},
    }


# -------------------------------------------------------
# FM-2. （旧 checkout フロー・後方互換で残す）
# -------------------------------------------------------
@router.post("/stripe/friend-manager-checkout")
async def create_friend_manager_checkout(data: dict, db: Session = Depends(get_db)):
    """後方互換。新規フローは FM-0 (setup-intent) を使うこと。"""
    user_id          = data.get("userId")
    new_friend_count = data.get("newFriendCount")
    if not user_id or new_friend_count is None:
        raise HTTPException(status_code=400, detail="userId と newFriendCount が必要です")

    new_friend_count = int(new_friend_count)
    extra = max(0, new_friend_count - FRIEND_FREE_LIMIT)
    if extra <= 0:
        return {"requires_payment": False, "monthly_amount": 0}

    amount = extra * PRICE_PER_FRIEND

    sub = db.execute(
        text("SELECT stripe_subscription_id, status, stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()

    try:
        customer_id = _get_or_create_stripe_customer(int(user_id), db)

        if sub and sub.stripe_subscription_id and sub.status == "active":
            subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            item_id = subscription["items"]["data"][0]["id"]
            new_price = stripe.Price.create(
                unit_amount=amount, currency="jpy",
                recurring={"interval": "month"},
                product_data={"name": "FRIEND's manager"},
                metadata={"user_id": str(user_id), "extra_count": str(extra)},
            )
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                items=[{"id": item_id, "price": new_price.id}],
                proration_behavior="none",
            )
            db.execute(text("""
                UPDATE friend_manager_subscriptions
                SET friend_count = :fc, charged_extra_count = :ec,
                    current_amount = :amt, updated_at = NOW()
                WHERE user_id = :uid
            """), {"fc": new_friend_count, "ec": extra, "amt": amount, "uid": int(user_id)})
            db.commit()
            return {"requires_payment": False, "updated": True, "monthly_amount": amount}

        today = datetime.now(timezone.utc).date()
        _, last_day = monthrange(today.year, today.month)
        days_until_end = last_day - today.day

        if days_until_end < 7:
            if today.month == 12:
                billing_start = date(today.year + 1, 1, 1)
            else:
                billing_start = date(today.year, today.month + 1, 1)
            trial_end = int(datetime(billing_start.year, billing_start.month, 1, tzinfo=timezone.utc).timestamp())
        else:
            billing_start = today
            trial_end = None

        price = stripe.Price.create(
            unit_amount=amount, currency="jpy",
            recurring={"interval": "month"},
            product_data={"name": "FRIEND's manager"},
            metadata={"user_id": str(user_id), "extra_count": str(extra)},
        )

        session_params: dict = {
            "customer": customer_id,
            "payment_method_types": ["card"],
            "line_items": [{"price": price.id, "quantity": 1}],
            "mode": "subscription",
            "success_url": f"{FRONTEND_URL}/friends?fm_session={{CHECKOUT_SESSION_ID}}",
            "cancel_url":  f"{FRONTEND_URL}/friends",
            "metadata": {
                "user_id": str(user_id), "product": "friend_manager",
                "extra_count": str(extra), "friend_count": str(new_friend_count),
                "billing_start": billing_start.isoformat(),
            },
        }
        if trial_end:
            session_params["subscription_data"] = {"trial_end": trial_end}

        session = stripe.checkout.Session.create(**session_params)

        existing = db.execute(
            text("SELECT id FROM friend_manager_subscriptions WHERE user_id = :uid"),
            {"uid": int(user_id)}
        ).fetchone()

        qp = {"uid": int(user_id), "cid": customer_id, "fc": new_friend_count,
              "ec": extra, "amt": amount, "bsd": billing_start}
        if not existing:
            db.execute(text("""
                INSERT INTO friend_manager_subscriptions
                    (user_id, stripe_customer_id, status, friend_count,
                     charged_extra_count, current_amount, billing_start_date)
                VALUES (:uid, :cid, 'pending', :fc, :ec, :amt, :bsd)
            """), qp)
        else:
            db.execute(text("""
                UPDATE friend_manager_subscriptions
                SET stripe_customer_id = :cid, status = 'pending',
                    friend_count = :fc, charged_extra_count = :ec,
                    current_amount = :amt, billing_start_date = :bsd
                WHERE user_id = :uid
            """), qp)
        db.commit()

        return {"requires_payment": True, "checkout_url": session.url,
                "monthly_amount": amount, "extra_count": extra}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# FM-3. サブスクリプション有効化（旧 Checkout 成功後）
# -------------------------------------------------------
@router.post("/stripe/friend-manager-activate")
async def activate_friend_manager(data: dict, db: Session = Depends(get_db)):
    session_id = data.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId が必要です")

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status not in ("paid", "no_payment_required"):
            raise HTTPException(status_code=403, detail="決済が完了していません")
        if stripe_session.metadata.get("product") != "friend_manager":
            raise HTTPException(status_code=400, detail="商品が一致しません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    user_id       = stripe_session.metadata.get("user_id")
    subscription_id = stripe_session.subscription
    extra_count   = int(stripe_session.metadata.get("extra_count", 0))
    friend_count  = int(stripe_session.metadata.get("friend_count", 0))
    amount        = extra_count * PRICE_PER_FRIEND

    db.execute(text("""
        UPDATE friend_manager_subscriptions
        SET stripe_subscription_id = :sid,
            status = 'active',
            friend_count = :fc,
            charged_extra_count = :ec,
            current_amount = :amt,
            updated_at = NOW()
        WHERE user_id = :uid
    """), {"sid": subscription_id, "fc": friend_count, "ec": extra_count,
           "amt": amount, "uid": int(user_id)})
    db.commit()

    return {"status": "activated", "monthly_amount": amount, "extra_count": extra_count}


# -------------------------------------------------------
# FM-4. サブスクリプションキャンセル
# -------------------------------------------------------
@router.post("/stripe/friend-manager-cancel")
async def cancel_friend_manager(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")

    sub = db.execute(
        text("SELECT stripe_subscription_id FROM friend_manager_subscriptions WHERE user_id = :uid AND status = 'active'"),
        {"uid": int(user_id)}
    ).fetchone()

    if not sub or not sub.stripe_subscription_id:
        return {"status": "no_active_subscription"}

    try:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    db.execute(text("""
        UPDATE friend_manager_subscriptions
        SET status = 'cancel_at_period_end', updated_at = NOW()
        WHERE user_id = :uid
    """), {"uid": int(user_id)})
    db.commit()

    return {"status": "cancel_scheduled"}

# ===============================================================
# 既存エンドポイント（変更なし）
# ===============================================================

# -------------------------------------------------------
# 1. Feeling LOG ダウンロード チェックアウト（200円）
# -------------------------------------------------------
@router.post("/stripe/feeling-log-checkout")
async def create_feeling_log_checkout(data: dict):
    user_id = data.get("userId") or data.get("profileId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": "Feeling Log ダウンロード"},
                    "unit_amount": PRICE_FEELING_LOG,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=data.get("successUrl", f"{FRONTEND_URL}/download/feeling-log?session_id={{CHECKOUT_SESSION_ID}}"),
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/profile"),
            metadata={"user_id": str(user_id), "product": "feeling_log"},
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# 2. Friends' Feeling Log チェックアウト（1,000円 / 30回）
# -------------------------------------------------------
@router.post("/stripe/friends-log-checkout")
async def create_friends_log_checkout(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")

    # 残クレジットがある購入が既にあれば重複購入を防ぐ
    existing = db.execute(text("""
        SELECT id, credits_remaining FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND credits_remaining > 0
        ORDER BY purchased_at DESC
        LIMIT 1
    """), {"uid": int(user_id)}).fetchone()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"残り{existing.credits_remaining}回分の購入が有効です。使い切ってから再購入してください。"
        )

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {
                        "name": "Friends' Feeling Log（30回分）",
                        "description": "Down Load 30 times of Friends' Feeling Log（1/EVERY 4HRS）"
                    },
                    "unit_amount": PRICE_FRIENDS_LOG,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{FRONTEND_URL}/?friends_log_session={{CHECKOUT_SESSION_ID}}",
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/"),
            metadata={"user_id": str(user_id), "product": "friends_log"},
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# 3. Friends' Feeling Log 購入アクティベート
# -------------------------------------------------------
@router.post("/stripe/friends-log-activate")
async def activate_friends_log(data: dict, db: Session = Depends(get_db)):
    session_id = data.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId が必要です")

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != "paid":
            raise HTTPException(status_code=403, detail="決済が完了していません")
        if stripe_session.metadata.get("product") != "friends_log":
            raise HTTPException(status_code=400, detail="商品が一致しません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    user_id = stripe_session.metadata.get("user_id")

    already = db.execute(text("""
        SELECT id, credits_remaining FROM friends_log_purchases
        WHERE stripe_session_id = :sid
    """), {"sid": session_id}).fetchone()

    if already:
        return {
            "status": "already_activated",
            "credits_remaining": already.credits_remaining,
        }

    db.execute(text("""
        INSERT INTO friends_log_purchases
            (buyer_user_id, stripe_session_id, purchased_at, expires_at, is_active, credits_remaining)
        VALUES (:uid, :sid, NOW(), NOW() + INTERVAL '60 days', true, 30)
    """), {"uid": int(user_id), "sid": session_id})
    db.commit()

    return {
        "status": "activated",
        "credits_remaining": 30,
    }


# -------------------------------------------------------
# 4. Friends' Feeling Log 購入状態チェック
# -------------------------------------------------------
FRIENDS_LOG_INTERVAL_HOURS = 4  # 次のDLまでの待機時間

@router.get("/stripe/friends-log-status")
async def get_friends_log_status(db: Session = Depends(get_db), user_id: int = None):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id が必要です")

    purchase = db.execute(text("""
        SELECT id, credits_remaining
        FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND credits_remaining > 0
          AND expires_at > NOW()
        ORDER BY purchased_at DESC
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    if not purchase:
        return {"has_active_purchase": False}

    # 最後のDL時刻を確認（4時間インターバルチェック）
    last_dl = db.execute(text("""
        SELECT downloaded_at FROM friends_log_downloads
        WHERE buyer_user_id = :uid
        ORDER BY downloaded_at DESC
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    now = datetime.now(timezone.utc)
    can_download = True
    next_available_at = None

    if last_dl and last_dl.downloaded_at:
        elapsed = now - last_dl.downloaded_at.replace(tzinfo=timezone.utc)
        if elapsed < timedelta(hours=FRIENDS_LOG_INTERVAL_HOURS):
            can_download = False
            next_available_at = (
                last_dl.downloaded_at.replace(tzinfo=timezone.utc)
                + timedelta(hours=FRIENDS_LOG_INTERVAL_HOURS)
            ).isoformat()

    return {
        "has_active_purchase": True,
        "credits_remaining": purchase.credits_remaining,
        "can_download": can_download,
        "next_available_at": next_available_at,  # can_download=False の時だけ値あり
    }


# -------------------------------------------------------
# 5. Friends' Feeling Log ダウンロード実行
# -------------------------------------------------------
@router.get("/download/friends-feeling-log")
async def download_friends_feeling_log(user_id: int, db: Session = Depends(get_db)):
    purchase = db.execute(text("""
        SELECT id, credits_remaining
        FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND credits_remaining > 0
        ORDER BY purchased_at DESC
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    if not purchase:
        raise HTTPException(status_code=403, detail="有効な購入がありません")

    # 4時間インターバルチェック
    last_dl = db.execute(text("""
        SELECT downloaded_at FROM friends_log_downloads
        WHERE buyer_user_id = :uid
        ORDER BY downloaded_at DESC
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    now = datetime.now(timezone.utc)
    if last_dl and last_dl.downloaded_at:
        elapsed = now - last_dl.downloaded_at.replace(tzinfo=timezone.utc)
        if elapsed < timedelta(hours=FRIENDS_LOG_INTERVAL_HOURS):
            remaining_minutes = int(
                (timedelta(hours=FRIENDS_LOG_INTERVAL_HOURS) - elapsed).total_seconds() / 60
            )
            raise HTTPException(
                status_code=429,
                detail=f"次のダウンロードまであと{remaining_minutes}分お待ちください。"
            )

    logs = db.execute(text("""
    SELECT DISTINCT ON (ml.user_id)
        u.nickname,
        u.username,
        ml.mood_type,
        ml.comment,
        ml.created_at
    FROM mood_logs ml
    JOIN users u ON u.id = ml.user_id
    WHERE ml.user_id IN (
        SELECT CASE
            WHEN f.user_id = :uid THEN f.friend_id
            ELSE f.user_id
        END
        FROM friendships f
        WHERE (f.user_id = :uid OR f.friend_id = :uid)
    )
    AND ml.is_visible = true
    AND ml.created_at > NOW() - INTERVAL '30 days'
    ORDER BY ml.user_id, ml.created_at DESC
"""), {"uid": user_id}).fetchall()

    db.execute(text("""
        INSERT INTO friends_log_downloads (buyer_user_id, downloaded_at)
        VALUES (:uid, NOW())
        ON CONFLICT (buyer_user_id)
        DO UPDATE SET downloaded_at = NOW()
    """), {"uid": user_id})

    # クレジットを1消費
    db.execute(text("""
        UPDATE friends_log_purchases
        SET credits_remaining = credits_remaining - 1
        WHERE id = :pid
    """), {"pid": purchase.id})

    db.commit()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["name", "date", "time", "mood", "emoji", "comment"])

    MOOD_EMOJI = {
        "happy": "😊", "excited": "🤩", "calm": "😌",
        "tired": "😥", "sad": "😭", "anxious": "😟",
        "angry": "😡", "neutral": "😐", "grateful": "🙏", "motivated": "🔥",
    }

    for log in logs:
        dt = log.created_at
        name = log.nickname or log.username
        writer.writerow([
            name,
            dt.strftime("%Y-%m-%d"),
            dt.strftime("%H:%M"),
            log.mood_type,
            MOOD_EMOJI.get(str(log.mood_type), ""),
            log.comment or "",
        ])

    output.seek(0)
    today_str = date.today().strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=friends_feeling_log_{today_str}.csv"},
    )


# -------------------------------------------------------
# 6. Feeling LOG（自分）ダウンロード実行
# -------------------------------------------------------
@router.get("/download/feeling-log")
async def download_feeling_log(session_id: str, db: Session = Depends(get_db)):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != "paid":
            raise HTTPException(status_code=403, detail="決済が完了していません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    user_id = session.metadata.get("user_id")

    result = db.execute(text("""
        SELECT created_at, mood_type, comment
        FROM mood_logs
        WHERE user_id = :user_id
          AND is_visible = true
          AND created_at > NOW() - INTERVAL '3 months'
        ORDER BY created_at DESC
        LIMIT 1000
    """), {"user_id": user_id})
    logs = result.fetchall()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["date", "time", "mood", "emoji", "comment"])

    MOOD_EMOJI = {
        "happy": "😊", "excited": "🤩", "calm": "😌",
        "tired": "😥", "sad": "😭", "anxious": "😟",
        "angry": "😡", "neutral": "😐", "grateful": "🙏", "motivated": "🔥",
    }

    for log in logs:
        dt = log.created_at
        writer.writerow([
            dt.strftime("%Y-%m-%d"),
            dt.strftime("%H:%M"),
            log.mood_type,
            MOOD_EMOJI.get(str(log.mood_type), ""),
            log.comment or "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=feeling_log.csv"},
    )


# -------------------------------------------------------
# 7. MEETUP 掲載料（500円）
# -------------------------------------------------------
@router.post("/stripe/meetup-checkout")
async def create_meetup_checkout(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    post_data = data.get("postData")  # フロントから投稿データを受け取る

    if not user_id or not post_data:
        raise HTTPException(status_code=400, detail="userId と postData が必要です")

    # ① 投稿を pending 状態で先に保存
    result = db.execute(text("""
        INSERT INTO hobby_posts (
            content, user_id, hobby_category_id, is_system,
            is_meetup, is_ad, is_hidden,
            meetup_date, meetup_location, meetup_capacity,
            meetup_fee_info, meetup_status
        ) VALUES (
            :content, :user_id, :hobby_category_id, false,
            true, false, true,
            :meetup_date, :meetup_location, :meetup_capacity,
            :meetup_fee_info, 'pending'
        ) RETURNING id
    """), {
        "content": post_data.get("content", ""),
        "user_id": int(user_id),
        "hobby_category_id": int(post_data.get("hobby_category_id", 1)),
        "meetup_date": post_data.get("meetup_date"),
        "meetup_location": post_data.get("meetup_location", ""),
        "meetup_capacity": post_data.get("meetup_capacity", 0),
        "meetup_fee_info": post_data.get("meetup_fee_info", ""),
    })
    db.commit()
    post_id = result.fetchone().id

    # ② Stripe Checkout Session を作成（post_id を紐づけ）
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": "MEETUP 掲載料"},
                    "unit_amount": PRICE_MEETUP,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{FRONTEND_URL}/community/{post_data.get('hobby_category_id')}?meetup_session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/community/{post_data.get('hobby_category_id')}?meetup_cancelled=true",
            metadata={
                "user_id": str(user_id),
                "product": "meetup",
                "post_id": str(post_id),
            },
        )

        # ③ stripe_session_id を投稿に紐づけ
        db.execute(text("""
            UPDATE hobby_posts
            SET stripe_session_id = :session_id
            WHERE id = :post_id
        """), {"session_id": session.id, "post_id": post_id})
        db.commit()

        return {"url": session.url, "post_id": post_id}

    except stripe.error.StripeError as e:
        # Stripe エラー時は pending 投稿を削除
        db.execute(text("DELETE FROM hobby_posts WHERE id = :post_id"), {"post_id": post_id})
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# 7-2. MEETUP アクティベート（支払い完了後）
# -------------------------------------------------------
@router.post("/stripe/meetup-activate")
async def activate_meetup(data: dict, db: Session = Depends(get_db)):
    session_id = data.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId が必要です")

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != "paid":
            raise HTTPException(status_code=403, detail="決済が完了していません")
        if stripe_session.metadata.get("product") != "meetup":
            raise HTTPException(status_code=400, detail="商品が一致しません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    post_id = stripe_session.metadata.get("post_id")

    # 投稿を公開状態に更新
    db.execute(text("""
        UPDATE hobby_posts
        SET meetup_status = 'open',
            is_hidden = false
        WHERE id = :post_id
    """), {"post_id": int(post_id)})
    db.commit()

    return {"status": "activated", "post_id": post_id}

# -------------------------------------------------------
# 8. アフェリエイトなし掲載（200円）
# -------------------------------------------------------
@router.post("/stripe/no-affiliate-checkout")
async def create_no_affiliate_checkout(data: dict):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": "アフェリエイトなし掲載"},
                    "unit_amount": PRICE_AFFILIATE_NONE,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=data.get("successUrl", f"{FRONTEND_URL}/profile?no_affiliate_paid=true"),
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/profile"),
            metadata={"user_id": str(user_id), "product": "no_affiliate"},
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# 9. AD 掲載（変動制）
# -------------------------------------------------------
@router.post("/stripe/ad-checkout")
async def create_ad_checkout(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    amount = data.get("amount")
    ad_title = data.get("adTitle", "広告掲載")
    ad_content = data.get("adContent", "")
    start_date = data.get("startDate")
    end_date = data.get("endDate")
    category_ids = data.get("categoryIds", [])
    ad_color = data.get("adColor", "green")

    if not user_id or not amount:
        raise HTTPException(status_code=400, detail="userId と amount が必要です")
    if int(amount) < 100:
        raise HTTPException(status_code=400, detail="最低金額は100円です")

    # ① 投稿を pending 状態で先に保存（複数カテゴリ対応）
    post_ids = []
    for category_id in category_ids:
        result = db.execute(text("""
            INSERT INTO hobby_posts (
                content, user_id, hobby_category_id, is_system,
                is_meetup, is_ad, is_hidden,
                ad_color, ad_start_date, ad_end_date, ad_status,
                meetup_status
            ) VALUES (
                :content, :user_id, :category_id, false,
                false, true, true,
                :ad_color, :start_date, :end_date, 'pending',
                'open'
            ) RETURNING id
        """), {
            "content": f"{ad_title}\n{ad_content}",
            "user_id": int(user_id),
            "category_id": int(category_id),
            "ad_color": ad_color,
            "start_date": start_date or None,
            "end_date": end_date or None,
        })
        db.commit()
        post_ids.append(result.fetchone().id)

    # ② Stripe Checkout Session を作成
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"AD 掲載：{ad_title}"},
                    "unit_amount": int(amount),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=data.get("successUrl", f"{FRONTEND_URL}/community?ad_session_id={{CHECKOUT_SESSION_ID}}"),
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/community"),
            metadata={
                "user_id": str(user_id),
                "product": "ad",
                "ad_title": ad_title,
                "post_ids": ",".join(str(i) for i in post_ids),
                "category_ids": ",".join(str(i) for i in category_ids),
            },
        )

        # ③ stripe_session_id を全投稿に紐づけ
        for post_id in post_ids:
            db.execute(text("""
                UPDATE hobby_posts
                SET stripe_session_id = :session_id
                WHERE id = :post_id
            """), {"session_id": session.id, "post_id": post_id})
        db.commit()

        return {"url": session.url, "post_ids": post_ids}

    except stripe.error.StripeError as e:
        # エラー時は pending 投稿を削除
        for post_id in post_ids:
            db.execute(text("DELETE FROM hobby_posts WHERE id = :post_id"), {"post_id": post_id})
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# 9-2. AD アクティベート（支払い完了後）
# -------------------------------------------------------
@router.post("/stripe/ad-activate")
async def activate_ad(data: dict, db: Session = Depends(get_db)):
    session_id = data.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId が必要です")

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != "paid":
            raise HTTPException(status_code=403, detail="決済が完了していません")
        if stripe_session.metadata.get("product") != "ad":
            raise HTTPException(status_code=400, detail="商品が一致しません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    post_ids_str = stripe_session.metadata.get("post_ids", "")
    post_ids = [int(i) for i in post_ids_str.split(",") if i]

    for post_id in post_ids:
        db.execute(text("""
            UPDATE hobby_posts
            SET ad_status = 'open',
                is_hidden = false
            WHERE id = :post_id
        """), {"post_id": post_id})
    db.commit()

    return {"status": "activated", "post_ids": post_ids}


# ===============================================================
# MEETUP 参加・決済フロー
# ===============================================================

MEETUP_CANCEL_FREE_HOUR = 0   # 当日0時以降はキャンセル料発生
MEETUP_COMMISSION_RATE  = 0.05  # 運営取り分 5%


def _get_or_create_stripe_customer_for_user(user_id: int, db: Session) -> str:
    """users テーブルから Stripe Customer を作成 or 取得（meetup用）"""
    row = db.execute(
        text("SELECT id, email, nickname FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    # post_responses に stripe_customer_id があればそれを使う
    existing = db.execute(
        text("""
            SELECT stripe_customer_id FROM post_responses
            WHERE user_id = :uid AND stripe_customer_id IS NOT NULL
            LIMIT 1
        """),
        {"uid": user_id}
    ).fetchone()

    if existing and existing.stripe_customer_id:
        return existing.stripe_customer_id

    # friend_manager_subscriptions にもあれば流用
    fm = db.execute(
        text("SELECT stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if fm and fm.stripe_customer_id:
        return fm.stripe_customer_id

    # 新規作成
    customer = stripe.Customer.create(
        email=row.email,
        name=row.nickname or f"user_{user_id}",
        metadata={"user_id": str(user_id)},
    )
    return customer.id


# -------------------------------------------------------
# M-1. JOIN時 SetupIntent（カード登録のみ・参加費ありの場合）
# -------------------------------------------------------
@router.post("/stripe/meetup-join-setup")
async def meetup_join_setup(data: dict, db: Session = Depends(get_db)):
    """
    参加費ありのMEETUPにJOINするとき、カードを登録させる。
    まだ課金しない。主催者が「開催決定」を押したときに課金する。
    """
    user_id  = data.get("userId")
    post_id  = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    # 投稿情報を取得
    post = db.execute(
        text("SELECT id, meetup_fee_info, content FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # Stripe Customer を作成 or 取得
    customer_id = _get_or_create_stripe_customer_for_user(user_id, db)

    # post_responses の stripe_customer_id を更新
    db.execute(text("""
        UPDATE post_responses
        SET stripe_customer_id = :cid
        WHERE user_id = :uid AND post_id = :pid
    """), {"cid": customer_id, "uid": user_id, "pid": post_id})
    db.commit()

    try:
        is_waitlist = data.get("isWaitlist", False)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            mode="setup",
            success_url=(
                f"{FRONTEND_URL}/community/{data.get('categoryId', '')}"
                f"?meetup_join_done=true&post_id={post_id}"
                f"&is_waitlist={'true' if is_waitlist else 'false'}"
                f"&setup_session_id={{CHECKOUT_SESSION_ID}}"
            ),
            cancel_url=f"{FRONTEND_URL}/community/{data.get('categoryId', '')}",
            metadata={
                "user_id":  str(user_id),
                "post_id":  str(post_id),
                "product":  "meetup_join",
            },
        )
        return {"checkout_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# M-1-2. JOIN SetupIntent完了後 → 参加レコード作成
# -------------------------------------------------------
@router.post("/stripe/meetup-join-complete")
async def meetup_join_complete(data: dict, db: Session = Depends(get_db)):
    user_id          = data.get("userId")
    post_id          = data.get("postId")
    setup_session_id = data.get("setupSessionId")
    is_waitlist      = data.get("isWaitlist", False)

    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    # SetupIntent完了確認
    try:
        session = stripe.checkout.Session.retrieve(setup_session_id)
        if session.status != "complete":
            raise HTTPException(status_code=403, detail="カード登録が完了していません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    # 既に参加レコードがあれば何もしない
    existing = db.execute(text("""
        SELECT id FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND is_participation = true
    """), {"uid": user_id, "pid": post_id}).fetchone()

    if existing:
        return {"status": "already_joined", "content": "Join!"}

    # contentを決定
    if is_waitlist:
        content = "Waitlist"
    else:
        # 定員確認
        post = db.execute(
            text("SELECT meetup_capacity FROM hobby_posts WHERE id = :pid"),
            {"pid": post_id}
        ).fetchone()
        current_count = db.execute(text("""
            SELECT COUNT(*) as cnt FROM post_responses
            WHERE post_id = :pid AND is_participation = true AND content != 'Waitlist'
        """), {"pid": post_id}).fetchone()

        content = "Waitlist" if current_count.cnt >= (post.meetup_capacity or 0) else "Join!"

    # 参加レコード作成
    db.execute(text("""
        INSERT INTO post_responses (user_id, post_id, content, is_participation, is_attended)
        VALUES (:uid, :pid, :content, true, false)
    """), {"uid": user_id, "pid": post_id, "content": content})

    # stripe_customer_idを更新
    customer_id = _get_or_create_stripe_customer_for_user(user_id, db)
    db.execute(text("""
        UPDATE post_responses
        SET stripe_customer_id = :cid
        WHERE user_id = :uid AND post_id = :pid
    """), {"cid": customer_id, "uid": user_id, "pid": post_id})

    db.commit()
    return {"status": "joined", "content": content}

# -------------------------------------------------------
# M-1-3. Waitlist → 参加昇格（50%オフ課金）
# -------------------------------------------------------
@router.post("/stripe/meetup-waitlist-join")
async def meetup_waitlist_join(data: dict, db: Session = Depends(get_db)):
    """
    Waitlistの人が「参加する」を押したとき。
    参加費がある場合は50%オフで課金。
    カード登録済みなら即課金、未登録ならSetupIntentへ。
    """
    user_id = data.get("userId")
    post_id = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    # Waitlistレコード確認
    response = db.execute(text("""
        SELECT id, stripe_customer_id
        FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND content = 'Waitlist'
    """), {"uid": user_id, "pid": post_id}).fetchone()

    if not response:
        raise HTTPException(status_code=404, detail="Waitlistレコードが見つかりません")

    # 投稿情報
    post = db.execute(
        text("SELECT meetup_fee_info, hobby_category_id FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()

    try:
        fee = int(post.meetup_fee_info or 0)
    except (TypeError, ValueError):
        fee = 0

    discount_fee = fee // 2  # 50%オフ

    # カード登録済みの場合 → 即課金
    if response.stripe_customer_id and discount_fee > 0:
        try:
            pms = stripe.PaymentMethod.list(
                customer=response.stripe_customer_id, type="card"
            )
            if pms.data:
                stripe.PaymentIntent.create(
                    amount=discount_fee,
                    currency="jpy",
                    customer=response.stripe_customer_id,
                    payment_method=pms.data[0].id,
                    confirm=True,
                    off_session=True,
                    metadata={
                        "user_id": str(user_id),
                        "post_id": str(post_id),
                        "product": "meetup_waitlist_fee",
                    },
                )
                # Waitlist → Join!に昇格
                db.execute(text("""
                    UPDATE post_responses
                    SET content = 'Join!', cancel_charged_at = NOW()
                    WHERE id = :rid
                """), {"rid": response.id})
                db.commit()
                return {"status": "joined", "charged": discount_fee}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 参加費なし or カード未登録で参加費なし → 直接昇格
    if discount_fee == 0:
        db.execute(text("""
            UPDATE post_responses
            SET content = 'Join!'
            WHERE id = :rid
        """), {"rid": response.id})
        db.commit()
        return {"status": "joined", "charged": 0}

    # カード未登録で参加費あり → SetupIntentへ
    customer_id = _get_or_create_stripe_customer_for_user(user_id, db)
    db.execute(text("""
        UPDATE post_responses
        SET stripe_customer_id = :cid
        WHERE id = :rid
    """), {"cid": customer_id, "rid": response.id})
    db.commit()

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            mode="setup",
            success_url=(
                f"{FRONTEND_URL}/community/{post.hobby_category_id}"
                f"?meetup_waitlist_done=true&post_id={post_id}"
                f"&setup_session_id={{CHECKOUT_SESSION_ID}}"
            ),
            cancel_url=f"{FRONTEND_URL}/community/{post.hobby_category_id}",
            metadata={
                "user_id": str(user_id),
                "post_id": str(post_id),
                "product": "meetup_waitlist",
            },
        )
        return {"checkout_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------
# M-2. 主催者「開催決定」→ 参加者全員に課金
# -------------------------------------------------------
@router.post("/stripe/meetup-confirm")
async def meetup_confirm(data: dict, db: Session = Depends(get_db)):
    """
    主催者が「開催決定」を押したとき。
    参加費ありの参加者全員のカードに一斉課金する。
    95%→主催者ConnectアカウントへTransfer / 5%→運営
    """
    post_id      = data.get("postId")
    organizer_id = data.get("organizerId")
    if not post_id or not organizer_id:
        raise HTTPException(status_code=400, detail="postId と organizerId が必要です")

    post_id      = int(post_id)
    organizer_id = int(organizer_id)

    # 投稿情報
    post = db.execute(
        text("SELECT id, meetup_fee_info, user_id FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.user_id != organizer_id:
        raise HTTPException(status_code=403, detail="主催者のみ操作できます")

    # 参加費を数値で取得
    try:
        fee = int(post.meetup_fee_info)
    except (TypeError, ValueError):
        # 参加費が数値でない（「お茶代各自」など）→ 課金スキップ
        db.execute(text("""
            UPDATE hobby_posts
            SET meetup_confirmed_at = NOW()
            WHERE id = :pid
        """), {"pid": post_id})
        db.commit()
        return {"status": "confirmed_no_charge", "message": "参加費なしのため課金スキップ"}

    if fee <= 0:
        db.execute(text("""
            UPDATE hobby_posts SET meetup_confirmed_at = NOW() WHERE id = :pid
        """), {"pid": post_id})
        db.commit()
        return {"status": "confirmed_no_charge"}

    # カード登録済みの参加者を取得
    participants = db.execute(text("""
        SELECT pr.user_id, pr.stripe_customer_id
        FROM post_responses pr
        WHERE pr.post_id = :pid
          AND pr.is_participation = true
          AND pr.stripe_customer_id IS NOT NULL
          AND pr.cancel_charged_at IS NULL
    """), {"pid": post_id}).fetchall()

    charged = []
    failed  = []

    for p in participants:
        try:
            # カードのPaymentMethodを取得
            pms = stripe.PaymentMethod.list(
                customer=p.stripe_customer_id, type="card"
            )
            if not pms.data:
                failed.append({"user_id": p.user_id, "reason": "no_card"})
                continue

            pm_id = pms.data[0].id

            # PaymentIntent で即時課金
            pi = stripe.PaymentIntent.create(
                amount=fee,
                currency="jpy",
                customer=p.stripe_customer_id,
                payment_method=pm_id,
                confirm=True,
                off_session=True,
                metadata={
                    "user_id":      str(p.user_id),
                    "post_id":      str(post_id),
                    "product":      "meetup_fee",
                    "organizer_id": str(organizer_id),
                },
            )
            charged.append({"user_id": p.user_id, "payment_intent_id": pi.id})

        except stripe.error.StripeError as e:
            failed.append({"user_id": p.user_id, "reason": str(e)})

    # 開催確定フラグを更新
    db.execute(text("""
        UPDATE hobby_posts
        SET meetup_confirmed_at = NOW()
        WHERE id = :pid
    """), {"pid": post_id})
    db.commit()

    # TODO: 主催者へのTransfer（Stripe Connect設定後に実装）
    # 現時点では課金だけ行い、主催者への送金は手動 or 後日実装

    return {
        "status":  "confirmed",
        "charged": len(charged),
        "failed":  len(failed),
        "details": {"charged": charged, "failed": failed},
    }


# -------------------------------------------------------
# M-3. 参加者キャンセル
# -------------------------------------------------------
@router.post("/stripe/meetup-cancel")
async def meetup_cancel(data: dict, db: Session = Depends(get_db)):
    """
    参加者がキャンセルするとき。
    前日23:59まで → 無料（post_responsesを削除）
    当日0時以降   → 50%徴収（カード登録済みの場合のみ）
                  → キャンセル待ちの最初の人に通知
    """
    user_id = data.get("userId")
    post_id = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    # 投稿情報（meetup_date と fee を確認）
    post = db.execute(
        text("SELECT meetup_date, meetup_fee_info FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # 参加レコード取得
    response = db.execute(text("""
        SELECT id, stripe_customer_id, content
        FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND is_participation = true
    """), {"uid": user_id, "pid": post_id}).fetchone()
    if not response:
        raise HTTPException(status_code=404, detail="参加レコードが見つかりません")

    now = datetime.now(timezone.utc)
    cancel_fee = 0
    is_same_day = False

    # 当日0時判定
    if post.meetup_date:
        meetup_day_start = post.meetup_date.replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        if now >= meetup_day_start:
            is_same_day = True

    # 当日キャンセル → 50%徴収
    if is_same_day and response.stripe_customer_id:
        try:
            fee = int(post.meetup_fee_info or 0)
        except (TypeError, ValueError):
            fee = 0

        if fee > 0:
            cancel_fee = fee // 2  # 50%
            try:
                pms = stripe.PaymentMethod.list(
                    customer=response.stripe_customer_id, type="card"
                )
                if pms.data:
                    stripe.PaymentIntent.create(
                        amount=cancel_fee,
                        currency="jpy",
                        customer=response.stripe_customer_id,
                        payment_method=pms.data[0].id,
                        confirm=True,
                        off_session=True,
                        metadata={
                            "user_id": str(user_id),
                            "post_id": str(post_id),
                            "product": "meetup_cancel_fee",
                        },
                    )
                    db.execute(text("""
                        UPDATE post_responses
                        SET cancel_charged_at = NOW()
                        WHERE id = :rid
                    """), {"rid": response.id})
            except stripe.error.StripeError:
                pass  # 課金失敗してもキャンセルは通す

    # post_responsesから削除（キャンセル待ちの人は残す）
    db.execute(text("""
        DELETE FROM post_responses
        WHERE id = :rid
    """), {"rid": response.id})

    # キャンセル待ち（content = 'Waitlist'）の最初の人を繰り上げ通知
    waitlist = db.execute(text("""
        SELECT pr.user_id, u.nickname
        FROM post_responses pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.post_id = :pid
          AND pr.content = 'Waitlist'
        ORDER BY pr.created_at ASC
        LIMIT 1
    """), {"pid": post_id}).fetchone()

    # キャンセル待ち全員に通知レコードを作成
    if waitlist:
        waitlist_all = db.execute(text("""
            SELECT pr.user_id
            FROM post_responses pr
            WHERE pr.post_id = :pid
              AND pr.content = 'Waitlist'
            ORDER BY pr.created_at ASC
        """), {"pid": post_id}).fetchall()

        post_info = db.execute(
            text("SELECT hobby_category_id, user_id FROM hobby_posts WHERE id = :pid"),
            {"pid": post_id}
        ).fetchone()

        for w in waitlist_all:
            try:
                db.execute(text("""
                    INSERT INTO notifications
                        (recipient_id, sender_id, hobby_category_id, message, event_post_id, is_read)
                    VALUES (:recipient, :sender, :cat_id, :msg, :post_id, false)
                """), {
                    "recipient": w.user_id,
                    "sender":    post_info.user_id,
                    "cat_id":    post_info.hobby_category_id,
                    "msg":       "キャンセルが出ました！参加できますか？",
                    "post_id":   post_id,
                })
            except Exception:
                pass

    db.commit()

    return {
        "status":      "cancelled",
        "cancel_fee":  cancel_fee,
        "is_same_day": is_same_day,
        "waitlist_notified": len(waitlist_all) if waitlist else 0,
    }


# -------------------------------------------------------
# M-4. 主催者 No Show マーク → 参加者全員100%徴収
#      または 参加者が「主催者来ない」を報告 → 返金
# -------------------------------------------------------
@router.post("/stripe/meetup-noshow")
async def meetup_noshow(data: dict, db: Session = Depends(get_db)):
    """
    type = 'organizer'  → 主催者が参加者のNo Showをマーク（100%課金）
    type = 'participant' → 参加者が主催者のNo Showを報告（全員返金 / 未課金なら何もしない）
    """
    post_id   = data.get("postId")
    user_id   = data.get("userId")    # 操作するユーザー
    target_id = data.get("targetId")  # No Showの対象（organizerの場合）
    ntype     = data.get("type", "organizer")  # 'organizer' or 'participant'

    if not post_id or not user_id:
        raise HTTPException(status_code=400, detail="postId と userId が必要です")

    post_id = int(post_id)
    user_id = int(user_id)

    post = db.execute(
        text("SELECT user_id, meetup_fee_info, meetup_organizer_showed FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    # ── 主催者が参加者のNo Showをマーク ──
    if ntype == "organizer":
        if post.user_id != user_id:
            raise HTTPException(status_code=403, detail="主催者のみ操作できます")
        if not target_id:
            raise HTTPException(status_code=400, detail="targetId が必要です")

        target_id = int(target_id)

        response = db.execute(text("""
            SELECT id, stripe_customer_id
            FROM post_responses
            WHERE user_id = :uid AND post_id = :pid AND is_participation = true
        """), {"uid": target_id, "pid": post_id}).fetchone()

        if not response or not response.stripe_customer_id:
            return {"status": "no_card_registered"}

        try:
            fee = int(post.meetup_fee_info or 0)
        except (TypeError, ValueError):
            fee = 0

        if fee > 0:
            pms = stripe.PaymentMethod.list(
                customer=response.stripe_customer_id, type="card"
            )
            if pms.data:
                try:
                    stripe.PaymentIntent.create(
                        amount=fee,
                        currency="jpy",
                        customer=response.stripe_customer_id,
                        payment_method=pms.data[0].id,
                        confirm=True,
                        off_session=True,
                        metadata={
                            "user_id": str(target_id),
                            "post_id": str(post_id),
                            "product": "meetup_noshow_fee",
                        },
                    )
                except stripe.error.StripeError as e:
                    raise HTTPException(status_code=500, detail=str(e))

        db.execute(text("""
            UPDATE post_responses
            SET is_attended = false, cancel_charged_at = NOW()
            WHERE id = :rid
        """), {"rid": response.id})
        db.commit()
        return {"status": "noshow_charged", "amount": fee}

    # ── 参加者が主催者のNo Showを報告 ──
    elif ntype == "participant":
        # 開催確定済みで課金されていたら返金
        charged = db.execute(text("""
            SELECT pr.user_id, pr.stripe_customer_id
            FROM post_responses pr
            WHERE pr.post_id = :pid
              AND pr.is_participation = true
              AND pr.cancel_charged_at IS NOT NULL
        """), {"pid": post_id}).fetchall()

        refunded = []
        for p in charged:
            try:
                # 最新のPaymentIntentを取得して返金
                pis = stripe.PaymentIntent.list(
                    customer=p.stripe_customer_id, limit=5
                )
                for pi in pis.data:
                    if (pi.metadata.get("post_id") == str(post_id)
                            and pi.metadata.get("product") == "meetup_fee"
                            and pi.status == "succeeded"):
                        stripe.Refund.create(payment_intent=pi.id)
                        refunded.append(p.user_id)
                        break
            except stripe.error.StripeError:
                pass

        # 主催者No Showフラグ
        db.execute(text("""
            UPDATE hobby_posts
            SET meetup_organizer_showed = false
            WHERE id = :pid
        """), {"pid": post_id})
        db.commit()

        return {
            "status":   "organizer_noshow_reported",
            "refunded": len(refunded),
            "user_ids": refunded,
        }

    raise HTTPException(status_code=400, detail="type は 'organizer' か 'participant' を指定してください")

# -------------------------------------------------------
# 10. Stripe Webhook（本番用）
# -------------------------------------------------------
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not WEBHOOK_SECRET:
        return {"status": "skipped"}

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Webhook署名が無効です")

    event_type = event["type"]
    stripe_session_obj = event["data"]["object"]

    # ---- checkout.session.completed ----
    if event_type == "checkout.session.completed":
        product = stripe_session_obj.get("metadata", {}).get("product", "")
        user_id = stripe_session_obj.get("metadata", {}).get("user_id")

        # Friends' Log 自動アクティベート
        if product == "friends_log" and user_id:
            already = db.execute(text(
                "SELECT id FROM friends_log_purchases WHERE stripe_session_id = :sid"
            ), {"sid": stripe_session_obj["id"]}).fetchone()

            if not already:
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                try:
                    db.execute(text("""
                        INSERT INTO friends_log_purchases
                            (buyer_user_id, stripe_session_id, purchased_at, expires_at, is_active)
                        VALUES (:uid, :sid, NOW(), :expires, true)
                    """), {
                        "uid": int(user_id),
                        "sid": stripe_session_obj["id"],
                        "expires": expires_at,
                    })
                    db.commit()
                except Exception:
                    db.rollback()

        # Friend Manager サブスク 自動アクティベート
        if product == "friend_manager" and user_id:
            subscription_id = stripe_session_obj.get("subscription")
            extra_count = int(stripe_session_obj.get("metadata", {}).get("extra_count", 0))
            friend_count = int(stripe_session_obj.get("metadata", {}).get("friend_count", 0))
            amount = extra_count * PRICE_PER_FRIEND
            try:
                db.execute(text("""
                    UPDATE friend_manager_subscriptions
                    SET stripe_subscription_id = :sid,
                        status = 'active',
                        friend_count = :fc,
                        charged_extra_count = :ec,
                        current_amount = :amt,
                        updated_at = NOW()
                    WHERE user_id = :uid
                """), {
                    "sid": subscription_id,
                    "fc": friend_count,
                    "ec": extra_count,
                    "amt": amount,
                    "uid": int(user_id),
                })
                db.commit()
            except Exception:
                db.rollback()

        # 支払い記録（一括払いのみ）
        if stripe_session_obj.get("mode") == "payment":
            try:
                db.execute(text("""
                    INSERT INTO stripe_payments (session_id, user_id, product, amount, paid_at)
                    VALUES (:session_id, :user_id, :product, :amount, NOW())
                    ON CONFLICT (session_id) DO NOTHING
                """), {
                    "session_id": stripe_session_obj["id"],
                    "user_id": user_id,
                    "product": product,
                    "amount": stripe_session_obj.get("amount_total", 0),
                })
                db.commit()
            except Exception:
                db.rollback()

    # ---- customer.subscription.deleted（サブスク終了）----
    elif event_type == "customer.subscription.deleted":
        subscription_id = stripe_session_obj.get("id")
        try:
            db.execute(text("""
                UPDATE friend_manager_subscriptions
                SET status = 'canceled', updated_at = NOW()
                WHERE stripe_subscription_id = :sid
            """), {"sid": subscription_id})
            db.commit()
        except Exception:
            db.rollback()

    # ---- invoice.payment_failed（支払い失敗）----
    elif event_type == "invoice.payment_failed":
        subscription_id = stripe_session_obj.get("subscription")
        if subscription_id:
            try:
                db.execute(text("""
                    UPDATE friend_manager_subscriptions
                    SET status = 'past_due', updated_at = NOW()
                    WHERE stripe_subscription_id = :sid
                """), {"sid": subscription_id})
                db.commit()
            except Exception:
                db.rollback()

    return {"status": "ok"}

# -------------------------------------------------------
# 11. 今月の課金サマリー（MyPage用）
#     - アクティブなサブスク（FRIEND's manager / hide_affiliate）
#     - 今月支払い済みの一時課金（feeling_log / meetup / ad / no_affiliate）
# -------------------------------------------------------
@router.get("/stripe/billing-summary")
async def get_billing_summary(user_id: int, db: Session = Depends(get_db)):
    """
    MyPageの課金一覧セクション用。
    今月1日以降に支払い済みの stripe_payments と
    アクティブなサブスク情報を返す。

    stripe_payments.user_id は VARCHAR で保存されているため
    CAST して比較する。テーブル未作成の場合も安全にスキップ。
    """
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── 今月の一時課金履歴 ──────────────────────────
    # user_id は VARCHAR 型で保存されているので文字列として比較
    one_time = []
    try:
        payments = db.execute(text("""
            SELECT product, amount, paid_at
            FROM stripe_payments
            WHERE user_id = :uid
              AND paid_at >= :month_start
            ORDER BY paid_at DESC
        """), {"uid": str(user_id), "month_start": month_start}).fetchall()

        PRODUCT_LABEL = {
            "feeling_log":  "Feeling Log DL",
            "friends_log":  "Friends' Log DL",
            "meetup":       "MEETUP 掲載",
            "ad":           "AD 掲載",
            "no_affiliate": "Hide affiliate ads",
        }

        one_time = [
            {
                "product": row.product,
                "amount":  row.amount,
                "paid_at": row.paid_at.isoformat(),
                "label":   PRODUCT_LABEL.get(row.product, row.product),
            }
            for row in payments
        ]
    except Exception:
        # stripe_payments テーブルが未作成の場合はスキップ
        pass

    # ── FRIEND's manager サブスク ────────────────────
    friend_manager = None
    try:
        fm_row = db.execute(text("""
            SELECT status, friend_count, charged_extra_count, current_amount
            FROM friend_manager_subscriptions
            WHERE user_id = :uid
              AND status IN ('active', 'pending', 'cancel_at_period_end', 'past_due')
            LIMIT 1
        """), {"uid": user_id}).fetchone()

        if fm_row:
            friend_manager = {
                "status":         fm_row.status,
                "friend_count":   fm_row.friend_count,
                "extra_count":    fm_row.charged_extra_count,
                "monthly_amount": fm_row.current_amount,
            }
    except Exception:
        # friend_manager_subscriptions テーブルが未作成の場合はスキップ
        pass

    # ── hide_affiliate サブスク ──────────────────────
    hide_affiliate_active = False
    try:
        ha_row = db.execute(text("""
            SELECT is_active FROM hide_affiliate_subscriptions
            WHERE user_id = :uid AND is_active = true
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        hide_affiliate_active = ha_row is not None
    except Exception:
        pass  # テーブルが未作成でも無視

    return {
        "friend_manager":    friend_manager,
        "hide_affiliate":    hide_affiliate_active,
        "one_time_payments": one_time,
    }