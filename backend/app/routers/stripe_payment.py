import csv
import io
import os
from datetime import datetime, timedelta, date, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

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
FRIEND_FREE_LIMIT    = 10    # 無料枠


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
    """友達数から月額を計算する。10人以下は0円。"""
    extra = max(0, friend_count - FRIEND_FREE_LIMIT)
    return extra * PRICE_PER_FRIEND


def _get_friend_count(user_id: int, db: Session) -> int:
    """現在の友達数を取得する。"""
    result = db.execute(text("""
        SELECT COUNT(*) AS cnt FROM friendships
        WHERE (user_id_1 = :uid OR user_id_2 = :uid)
          AND status = 'accepted'
    """), {"uid": user_id}).fetchone()
    return result.cnt if result else 0


# ===============================================================
# FRIEND's MANAGER エンドポイント
# ===============================================================

# -------------------------------------------------------
# FM-1. サブスクリプション状態チェック
# -------------------------------------------------------
@router.get("/stripe/friend-manager-status")
async def get_friend_manager_status(user_id: int, db: Session = Depends(get_db)):
    """
    フロントエンドが友達追加前後に呼び出し、課金状態を確認する。
    """
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
        "friend_count": friend_count,
        "free_limit": FRIEND_FREE_LIMIT,
        "extra_count": max(0, friend_count - FRIEND_FREE_LIMIT),
        "monthly_amount": amount,
        "subscription": {
            "exists": sub is not None,
            "status": sub.status if sub else "none",
            "subscription_id": sub.stripe_subscription_id if sub else None,
            "current_amount": sub.current_amount if sub else 0,
        } if sub else {"exists": False, "status": "none"},
    }


# -------------------------------------------------------
# FM-2. サブスクリプション作成 or 金額更新 チェックアウト
#        （11人目以降を友達追加するたびに呼び出す）
# -------------------------------------------------------
@router.post("/stripe/friend-manager-checkout")
async def create_friend_manager_checkout(data: dict, db: Session = Depends(get_db)):
    """
    友達数が FRIEND_FREE_LIMIT を超えている場合にサブスクを作成 or 更新する。

    フロントから渡すデータ:
        { "userId": 123, "newFriendCount": 11 }

    処理フロー:
    1. newFriendCount から月額を計算
    2. Stripe Customer を取得 or 作成
    3. 既存サブスクがあれば Stripe の Price を更新（proration なし）
    4. なければ新規サブスク作成のための Checkout Session を発行
    """
    user_id = data.get("userId")
    new_friend_count = data.get("newFriendCount")
    if not user_id or new_friend_count is None:
        raise HTTPException(status_code=400, detail="userId と newFriendCount が必要です")

    new_friend_count = int(new_friend_count)
    extra = max(0, new_friend_count - FRIEND_FREE_LIMIT)
    if extra <= 0:
        # 10人以下なら課金不要
        return {"requires_payment": False, "monthly_amount": 0}

    amount = extra * PRICE_PER_FRIEND

    # 既存サブスクを確認
    sub = db.execute(
        text("SELECT stripe_subscription_id, status, stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()

    try:
        customer_id = _get_or_create_stripe_customer(int(user_id), db)

        # ---- サブスクが既にアクティブ → 金額を更新して完了 ----
        if sub and sub.stripe_subscription_id and sub.status == "active":
            subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            item_id = subscription["items"]["data"][0]["id"]

            # 新しい Price を都度作成（メタデータで管理）
            new_price = stripe.Price.create(
                unit_amount=amount,
                currency="jpy",
                recurring={"interval": "month"},
                product_data={"name": "FRIEND's manager"},
                metadata={"user_id": str(user_id), "extra_count": str(extra)},
            )

            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                items=[{"id": item_id, "price": new_price.id}],
                proration_behavior="none",
            )

            # DBを更新
            db.execute(text("""
                UPDATE friend_manager_subscriptions
                SET friend_count = :fc,
                    charged_extra_count = :ec,
                    current_amount = :amt,
                    updated_at = NOW()
                WHERE user_id = :uid
            """), {"fc": new_friend_count, "ec": extra, "amt": amount, "uid": int(user_id)})
            db.commit()

            return {
                "requires_payment": False,
                "updated": True,
                "monthly_amount": amount,
                "extra_count": extra,
            }

        # ---- サブスク未作成 or キャンセル済み → Checkout Session を発行 ----
        # Stripe Price を作成
        price = stripe.Price.create(
            unit_amount=amount,
            currency="jpy",
            recurring={"interval": "month"},
            product_data={"name": "FRIEND's manager"},
            metadata={"user_id": str(user_id), "extra_count": str(extra)},
        )

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price.id, "quantity": 1}],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/friends?fm_session={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/friends",
            metadata={
                "user_id": str(user_id),
                "product": "friend_manager",
                "extra_count": str(extra),
                "friend_count": str(new_friend_count),
            },
        )

        # customer_id を DB に保存（サブスクはWebhook完了後に保存）
        existing = db.execute(
            text("SELECT id FROM friend_manager_subscriptions WHERE user_id = :uid"),
            {"uid": int(user_id)}
        ).fetchone()
        if not existing:
            db.execute(text("""
                INSERT INTO friend_manager_subscriptions
                    (user_id, stripe_customer_id, status, friend_count, charged_extra_count, current_amount)
                VALUES (:uid, :cid, 'pending', :fc, :ec, :amt)
            """), {"uid": int(user_id), "cid": customer_id, "fc": new_friend_count, "ec": extra, "amt": amount})
        else:
            db.execute(text("""
                UPDATE friend_manager_subscriptions
                SET stripe_customer_id = :cid, status = 'pending',
                    friend_count = :fc, charged_extra_count = :ec, current_amount = :amt
                WHERE user_id = :uid
            """), {"cid": customer_id, "fc": new_friend_count, "ec": extra, "amt": amount, "uid": int(user_id)})
        db.commit()

        return {
            "requires_payment": True,
            "checkout_url": session.url,
            "monthly_amount": amount,
            "extra_count": extra,
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# FM-3. サブスクリプション有効化（Checkout成功後）
# -------------------------------------------------------
@router.post("/stripe/friend-manager-activate")
async def activate_friend_manager(data: dict, db: Session = Depends(get_db)):
    """
    フロントエンドが success_url から session_id を受け取り呼び出す。
    """
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

    user_id = stripe_session.metadata.get("user_id")
    subscription_id = stripe_session.subscription
    extra_count = int(stripe_session.metadata.get("extra_count", 0))
    friend_count = int(stripe_session.metadata.get("friend_count", 0))
    amount = extra_count * PRICE_PER_FRIEND

    db.execute(text("""
        UPDATE friend_manager_subscriptions
        SET stripe_subscription_id = :sid,
            status = 'active',
            friend_count = :fc,
            charged_extra_count = :ec,
            current_amount = :amt,
            updated_at = NOW()
        WHERE user_id = :uid
    """), {"sid": subscription_id, "fc": friend_count, "ec": extra_count, "amt": amount, "uid": int(user_id)})
    db.commit()

    return {"status": "activated", "monthly_amount": amount, "extra_count": extra_count}


# -------------------------------------------------------
# FM-4. サブスクリプションキャンセル（友達を10人以下に減らした場合）
# -------------------------------------------------------
@router.post("/stripe/friend-manager-cancel")
async def cancel_friend_manager(data: dict, db: Session = Depends(get_db)):
    """
    友達が10人以下になったらサブスクをキャンセルする。
    フロントから: { "userId": 123 }
    """
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
        # 期末キャンセル（月末まで有効）
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
        )
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
# 2. Friends' Feeling Log チェックアウト（1,000円 / 30日）
# -------------------------------------------------------
@router.post("/stripe/friends-log-checkout")
async def create_friends_log_checkout(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")

    existing = db.execute(text("""
        SELECT id, expires_at FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND expires_at > NOW()
        ORDER BY expires_at DESC
        LIMIT 1
    """), {"uid": int(user_id)}).fetchone()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"有効な購入が既にあります。期限: {existing.expires_at.strftime('%Y/%m/%d')}"
        )

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "product_data": {
                        "name": "Friends' Feeling Log（30日間・1日1回DL）",
                        "description": "購入後30日間、友達全員のFeeling Logを毎日1回ダウンロードできます"
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
        SELECT id FROM friends_log_purchases WHERE stripe_session_id = :sid
    """), {"sid": session_id}).fetchone()

    if already:
        purchase = db.execute(text("""
            SELECT expires_at,
                   (expires_at::date - CURRENT_DATE) AS days_remaining
            FROM friends_log_purchases
            WHERE stripe_session_id = :sid
        """), {"sid": session_id}).fetchone()
        return {
            "status": "already_activated",
            "days_remaining": purchase.days_remaining,
            "expires_at": purchase.expires_at.isoformat(),
        }

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.execute(text("""
        INSERT INTO friends_log_purchases
            (buyer_user_id, stripe_session_id, purchased_at, expires_at, is_active)
        VALUES (:uid, :sid, NOW(), :expires, true)
    """), {"uid": int(user_id), "sid": session_id, "expires": expires_at})
    db.commit()

    return {
        "status": "activated",
        "days_remaining": 30,
        "expires_at": expires_at.isoformat(),
    }


# -------------------------------------------------------
# 4. Friends' Feeling Log 購入状態チェック
# -------------------------------------------------------
@router.get("/stripe/friends-log-status")
async def get_friends_log_status(db: Session = Depends(get_db), user_id: int = None):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id が必要です")

    purchase = db.execute(text("""
        SELECT
            expires_at,
            (expires_at::date - CURRENT_DATE) AS days_remaining
        FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND expires_at > NOW()
        ORDER BY expires_at DESC
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    if not purchase:
        return {"has_active_purchase": False}

    already_downloaded_today = db.execute(text("""
        SELECT id FROM friends_log_downloads
        WHERE buyer_user_id = :uid
          AND download_date = CURRENT_DATE
    """), {"uid": user_id}).fetchone()

    return {
        "has_active_purchase": True,
        "days_remaining": max(0, purchase.days_remaining),
        "expires_at": purchase.expires_at.isoformat(),
        "can_download_today": already_downloaded_today is None,
    }


# -------------------------------------------------------
# 5. Friends' Feeling Log ダウンロード実行
# -------------------------------------------------------
@router.get("/download/friends-feeling-log")
async def download_friends_feeling_log(user_id: int, db: Session = Depends(get_db)):
    purchase = db.execute(text("""
        SELECT id FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND expires_at > NOW()
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    if not purchase:
        raise HTTPException(status_code=403, detail="有効な購入がありません")

    already = db.execute(text("""
        SELECT id FROM friends_log_downloads
        WHERE buyer_user_id = :uid
          AND download_date = CURRENT_DATE
    """), {"uid": user_id}).fetchone()

    if already:
        raise HTTPException(
            status_code=429,
            detail="本日のダウンロードは完了しています。明日また試してください。"
        )

    logs = db.execute(text("""
        SELECT
            u.nickname,
            u.username,
            ml.mood_type,
            ml.comment,
            ml.created_at
        FROM mood_logs ml
        JOIN users u ON u.id = ml.user_id
        WHERE ml.user_id IN (
            SELECT CASE
                WHEN f.user_id_1 = :uid THEN f.user_id_2
                ELSE f.user_id_1
            END
            FROM friendships f
            WHERE (f.user_id_1 = :uid OR f.user_id_2 = :uid)
              AND f.status = 'accepted'
        )
        AND ml.is_visible = true
        AND ml.created_at > NOW() - INTERVAL '30 days'
        ORDER BY ml.created_at DESC
        LIMIT 3000
    """), {"uid": user_id}).fetchall()

    db.execute(text("""
        INSERT INTO friends_log_downloads (buyer_user_id, download_date)
        VALUES (:uid, CURRENT_DATE)
        ON CONFLICT (buyer_user_id, download_date) DO NOTHING
    """), {"uid": user_id})
    db.commit()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["name", "date", "time", "mood", "emoji", "comment"])

    MOOD_EMOJI = {
        "happy": "😊", "excited": "🤩", "calm": "😌",
        "tired": "😥", "sad": "😭", "anxious": "😟",
        "angry": "😠", "neutral": "😐", "grateful": "🙏", "motivated": "🔥",
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
        "angry": "😠", "neutral": "😐", "grateful": "🙏", "motivated": "🔥",
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
async def create_meetup_checkout(data: dict):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")
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
            success_url=data.get("successUrl", f"{FRONTEND_URL}/community?meetup_paid=true"),
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/community"),
            metadata={"user_id": str(user_id), "product": "meetup"},
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


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
async def create_ad_checkout(data: dict):
    user_id = data.get("userId")
    amount = data.get("amount")
    ad_title = data.get("adTitle", "広告掲載")
    if not user_id or not amount:
        raise HTTPException(status_code=400, detail="userId と amount が必要です")
    if int(amount) < 100:
        raise HTTPException(status_code=400, detail="最低金額は100円です")
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
            success_url=data.get("successUrl", f"{FRONTEND_URL}/community?ad_paid=true"),
            cancel_url=data.get("cancelUrl", f"{FRONTEND_URL}/community"),
            metadata={"user_id": str(user_id), "product": "ad", "ad_title": ad_title},
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


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