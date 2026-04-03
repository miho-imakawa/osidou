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
from ..utils.email import send_email, meetup_confirmed_email_html

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
# MEETUP 設定定数
# ===============================================================
MEETUP_ORGANIZER_CANCEL_HOURS = 24   # 主催者キャンセル期限：開催24時間前まで
MEETUP_COMMISSION_RATE        = 0.05 # 運営取り分 5%（主催者95%）
ORGANIZER_CONNECT_ACCOUNT_ID  = os.getenv("STRIPE_CONNECT_ACCOUNT_ID", "")  # 主催者へのTransfer用（Connect設定後）


# ===============================================================
# FRIEND's MANAGER ユーティリティ
# ===============================================================

def _get_or_create_stripe_customer(user_id: int, db: Session) -> str:
    row = db.execute(
        text("SELECT id, email, nickname FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    sub_row = db.execute(
        text("SELECT stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()

    if sub_row and sub_row.stripe_customer_id:
        return sub_row.stripe_customer_id

    customer = stripe.Customer.create(
        email=row.email,
        name=row.nickname or f"user_{user_id}",
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def _calc_amount(friend_count: int) -> int:
    extra = max(0, friend_count - FRIEND_FREE_LIMIT)
    return extra * PRICE_PER_FRIEND


def _get_friend_count(user_id: int, db: Session) -> int:
    result = db.execute(text("""
        SELECT COUNT(*) AS cnt FROM friendships
        WHERE user_id = :uid
    """), {"uid": user_id}).fetchone()
    return result.cnt if result else 0


def _create_subscription_for_requester(requester_id: int, db: Session) -> dict:
    friend_count = _get_friend_count(requester_id, db)
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

    if not sub_row or not sub_row.stripe_customer_id:
        return {"requires_payment": False, "skipped": True}

    customer_id = sub_row.stripe_customer_id

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

    payment_methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
    if not payment_methods.data:
        return {"requires_payment": False, "skipped": True, "reason": "no_payment_method"}

    pm_id = payment_methods.data[0].id
    stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": pm_id})

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

@router.post("/stripe/friend-manager-setup-intent")
async def create_friend_manager_setup_intent(data: dict, db: Session = Depends(get_db)):
    requester_id = data.get("requesterId")
    receiver_id  = data.get("receiverId")
    if not requester_id or not receiver_id:
        raise HTTPException(status_code=400, detail="requesterId と receiverId が必要です")

    requester_id = int(requester_id)
    receiver_id  = int(receiver_id)

    customer_id = _get_or_create_stripe_customer(requester_id, db)

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


@router.post("/stripe/friend-manager-checkout")
async def create_friend_manager_checkout(data: dict, db: Session = Depends(get_db)):
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


@router.post("/stripe/friends-log-checkout")
async def create_friends_log_checkout(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")

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


FRIENDS_LOG_INTERVAL_HOURS = 4

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
        "next_available_at": next_available_at,
    }


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
        u.nickname, u.username, ml.mood_type, ml.created_at,
        CASE 
            WHEN u.is_mood_comment_visible = true 
             AND f.is_muted = false 
            THEN ml.comment 
            ELSE NULL 
        END AS comment
    FROM mood_logs ml
    JOIN users u ON u.id = ml.user_id
    JOIN friendships f ON f.friend_id = ml.user_id AND f.user_id = :uid
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
    post_data = data.get("postData")

    if not user_id or not post_data:
        raise HTTPException(status_code=400, detail="userId と postData が必要です")

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

        db.execute(text("""
            UPDATE hobby_posts
            SET stripe_session_id = :session_id
            WHERE id = :post_id
        """), {"session_id": session.id, "post_id": post_id})
        db.commit()

        return {"url": session.url, "post_id": post_id}

    except stripe.error.StripeError as e:
        db.execute(text("DELETE FROM hobby_posts WHERE id = :post_id"), {"post_id": post_id})
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


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

    db.execute(text("""
        UPDATE hobby_posts
        SET meetup_status = 'open',
            is_hidden = false
        WHERE id = :post_id
    """), {"post_id": int(post_id)})
    db.commit()

    return {"status": "activated", "post_id": post_id}


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

        for post_id in post_ids:
            db.execute(text("""
                UPDATE hobby_posts
                SET stripe_session_id = :session_id
                WHERE id = :post_id
            """), {"session_id": session.id, "post_id": post_id})
        db.commit()

        return {"url": session.url, "post_ids": post_ids}

    except stripe.error.StripeError as e:
        for post_id in post_ids:
            db.execute(text("DELETE FROM hobby_posts WHERE id = :post_id"), {"post_id": post_id})
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


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

def _get_or_create_stripe_customer_for_user(user_id: int, db: Session) -> str:
    row = db.execute(
        text("SELECT id, email, nickname FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

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

    fm = db.execute(
        text("SELECT stripe_customer_id FROM friend_manager_subscriptions WHERE user_id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if fm and fm.stripe_customer_id:
        return fm.stripe_customer_id

    customer = stripe.Customer.create(
        email=row.email,
        name=row.nickname or f"user_{user_id}",
        metadata={"user_id": str(user_id)},
    )
    return customer.id


@router.post("/stripe/meetup-join-setup")
async def meetup_join_setup(data: dict, db: Session = Depends(get_db)):
    user_id  = data.get("userId")
    post_id  = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    post = db.execute(
        text("SELECT id, meetup_fee_info, content FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    customer_id = _get_or_create_stripe_customer_for_user(user_id, db)

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

    try:
        session = stripe.checkout.Session.retrieve(setup_session_id)
        if session.status != "complete":
            raise HTTPException(status_code=403, detail="カード登録が完了していません")
    except stripe.error.StripeError:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    existing = db.execute(text("""
        SELECT id FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND is_participation = true
    """), {"uid": user_id, "pid": post_id}).fetchone()

    if existing:
        return {"status": "already_joined", "content": "Join!"}

    if is_waitlist:
        content = "Waitlist"
    else:
        post = db.execute(
            text("SELECT meetup_capacity FROM hobby_posts WHERE id = :pid"),
            {"pid": post_id}
        ).fetchone()
        current_count = db.execute(text("""
            SELECT COUNT(*) as cnt FROM post_responses
            WHERE post_id = :pid AND is_participation = true AND content != 'Waitlist'
        """), {"pid": post_id}).fetchone()

        content = "Waitlist" if current_count.cnt >= (post.meetup_capacity or 0) else "Join!"

    db.execute(text("""
        INSERT INTO post_responses (user_id, post_id, content, is_participation, is_attended)
        VALUES (:uid, :pid, :content, true, false)
    """), {"uid": user_id, "pid": post_id, "content": content})

    customer_id = _get_or_create_stripe_customer_for_user(user_id, db)
    db.execute(text("""
        UPDATE post_responses
        SET stripe_customer_id = :cid
        WHERE user_id = :uid AND post_id = :pid
    """), {"cid": customer_id, "uid": user_id, "pid": post_id})

    db.commit()
    return {"status": "joined", "content": content}


@router.post("/stripe/meetup-waitlist-join")
async def meetup_waitlist_join(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("userId")
    post_id = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    response = db.execute(text("""
        SELECT id, stripe_customer_id
        FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND content = 'Waitlist'
    """), {"uid": user_id, "pid": post_id}).fetchone()

    if not response:
        raise HTTPException(status_code=404, detail="Waitlistレコードが見つかりません")

    post = db.execute(
        text("SELECT meetup_fee_info, hobby_category_id FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()

    try:
        fee = int(post.meetup_fee_info or 0)
    except (TypeError, ValueError):
        fee = 0

    discount_fee = fee // 2

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
                db.execute(text("""
                    UPDATE post_responses
                    SET content = 'Join!', cancel_charged_at = NOW()
                    WHERE id = :rid
                """), {"rid": response.id})
                db.commit()
                return {"status": "joined", "charged": discount_fee}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    if discount_fee == 0:
        db.execute(text("""
            UPDATE post_responses
            SET content = 'Join!'
            WHERE id = :rid
        """), {"rid": response.id})
        db.commit()
        return {"status": "joined", "charged": 0}

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
# M-2. 主催者「開催決定」→ 参加者全員に課金（主催者95% / 運営5%）
# -------------------------------------------------------
@router.post("/stripe/meetup-confirm")
async def meetup_confirm(data: dict, db: Session = Depends(get_db)):
    """
    主催者が「開催決定」を押したとき。
    参加費ありの参加者全員のカードに一斉課金する。
    ✅ 取り分：主催者95% / 運営5%
    ※ Stripe Connect設定済みの場合、organizer_connect_account_idへTransferする。
    """
    post_id      = data.get("postId")
    organizer_id = data.get("organizerId")
    if not post_id or not organizer_id:
        raise HTTPException(status_code=400, detail="postId と organizerId が必要です")

    post_id      = int(post_id)
    organizer_id = int(organizer_id)

    post = db.execute(
        text("SELECT id, meetup_fee_info, user_id FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.user_id != organizer_id:
        raise HTTPException(status_code=403, detail="主催者のみ操作できます")

    try:
        fee = int(post.meetup_fee_info)
    except (TypeError, ValueError):
        db.execute(text("""
            UPDATE hobby_posts SET meetup_confirmed_at = NOW() WHERE id = :pid
        """), {"pid": post_id})
        db.commit()
        return {"status": "confirmed_no_charge", "message": "参加費なしのため課金スキップ"}

    if fee <= 0:
        db.execute(text("""
            UPDATE hobby_posts SET meetup_confirmed_at = NOW() WHERE id = :pid
        """), {"pid": post_id})
        db.commit()
        return {"status": "confirmed_no_charge"}

    # 主催者へのTransfer金額（95%）
    organizer_amount = int(fee * (1 - MEETUP_COMMISSION_RATE))  # 参加費の95%
    commission_amount = fee - organizer_amount                   # 運営取り分5%

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
            pms = stripe.PaymentMethod.list(
                customer=p.stripe_customer_id, type="card"
            )
            if not pms.data:
                failed.append({"user_id": p.user_id, "reason": "no_card"})
                continue

            pm_id = pms.data[0].id

            # PaymentIntent で課金（全額）
            pi_params: dict = {
                "amount": fee,
                "currency": "jpy",
                "customer": p.stripe_customer_id,
                "payment_method": pm_id,
                "confirm": True,
                "off_session": True,
                "metadata": {
                    "user_id":           str(p.user_id),
                    "post_id":           str(post_id),
                    "product":           "meetup_fee",
                    "organizer_id":      str(organizer_id),
                    "organizer_amount":  str(organizer_amount),
                    "commission_amount": str(commission_amount),
                },
            }

            # ✅ Stripe Connect設定済みの場合：主催者アカウントへ95%をTransfer
            # 環境変数 STRIPE_CONNECT_ACCOUNT_ID が設定されていれば自動Transfer
            organizer = db.execute(
                text("SELECT stripe_connect_account_id, stripe_connect_onboarded FROM users WHERE id = :uid"),
                {"uid": organizer_id}
            ).fetchone()

            if organizer and organizer.stripe_connect_account_id and organizer.stripe_connect_onboarded:
                pi_params["transfer_data"] = {
                    "amount": organizer_amount,
                    "destination": organizer.stripe_connect_account_id,
                }

            pi = stripe.PaymentIntent.create(**pi_params)
            charged.append({
                "user_id":           p.user_id,
                "payment_intent_id": pi.id,
                "charged":           fee,
                "organizer_gets":    organizer_amount,
                "commission":        commission_amount,
            })

        except stripe.error.StripeError as e:
            failed.append({"user_id": p.user_id, "reason": str(e)})

    db.execute(text("""
        UPDATE hobby_posts
        SET meetup_confirmed_at = NOW()
        WHERE id = :pid
    """), {"pid": post_id})
    db.commit()

    # 支払い完了メール（参加者全員に）
    for c in charged:
        user_row = db.execute(
            text("SELECT email, nickname FROM users WHERE id = :uid"),
            {"uid": c["user_id"]}
        ).fetchone()
        if user_row and user_row.email:
            asyncio.create_task(send_email(
                to=user_row.email,
                subject="【推し道】MEETUP参加費のお支払いが完了しました",
                html=meetup_confirmed_email_html(
                    user_row.nickname or "",
                    post_info.content[:30] if hasattr(post_info, 'content') else "MEETUP",
                    fee,
                ),
            ))

    return {
        "status":            "confirmed",
        "charged":           len(charged),
        "failed":            len(failed),
        "organizer_rate":    f"{int((1 - MEETUP_COMMISSION_RATE) * 100)}%",
        "commission_rate":   f"{int(MEETUP_COMMISSION_RATE * 100)}%",
        "details":           {"charged": charged, "failed": failed},
    }


# -------------------------------------------------------
# M-3. 参加者キャンセル（24時間前まで無料）
# -------------------------------------------------------
@router.post("/stripe/meetup-cancel")
async def meetup_cancel(data: dict, db: Session = Depends(get_db)):
    """
    参加者がキャンセルするとき。
    ✅ 開催24時間前より前   → 無料キャンセル
    ✅ 開催24時間前以降     → 50%キャンセル料発生
    ✅ 当日0時以降          → 50%キャンセル料発生（従来どおり）
    キャンセル待ちの全員に通知。
    """
    user_id = data.get("userId")
    post_id = data.get("postId")
    if not user_id or not post_id:
        raise HTTPException(status_code=400, detail="userId と postId が必要です")

    user_id = int(user_id)
    post_id = int(post_id)

    post = db.execute(
        text("SELECT meetup_date, meetup_fee_info FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    response = db.execute(text("""
        SELECT id, stripe_customer_id, content
        FROM post_responses
        WHERE user_id = :uid AND post_id = :pid AND is_participation = true
    """), {"uid": user_id, "pid": post_id}).fetchone()
    if not response:
        raise HTTPException(status_code=404, detail="参加レコードが見つかりません")

    now = datetime.now(timezone.utc)
    cancel_fee = 0
    is_chargeable = False  # キャンセル料が発生するか

    # ✅ 開催24時間前チェック
    if post.meetup_date:
        meetup_dt = post.meetup_date
        # tzinfoがない場合はUTCとして扱う
        if meetup_dt.tzinfo is None:
            meetup_dt = meetup_dt.replace(tzinfo=timezone.utc)

        cancel_deadline = meetup_dt - timedelta(hours=MEETUP_ORGANIZER_CANCEL_HOURS)

        if now >= cancel_deadline:
            # 24時間前を過ぎている → キャンセル料発生
            is_chargeable = True

    # キャンセル料計算（50%）
    if is_chargeable and response.stripe_customer_id:
        try:
            fee = int(post.meetup_fee_info or 0)
        except (TypeError, ValueError):
            fee = 0

        if fee > 0:
            cancel_fee = fee // 2
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

    # 参加レコード削除
    db.execute(text("DELETE FROM post_responses WHERE id = :rid"), {"rid": response.id})

    # キャンセル待ち全員に通知
    waitlist = db.execute(text("""
        SELECT pr.user_id
        FROM post_responses pr
        WHERE pr.post_id = :pid AND pr.content = 'Waitlist'
        ORDER BY pr.created_at ASC
    """), {"pid": post_id}).fetchall()

    waitlist_count = 0
    if waitlist:
        post_info = db.execute(
            text("SELECT hobby_category_id, user_id FROM hobby_posts WHERE id = :pid"),
            {"pid": post_id}
            ).fetchone()

    for w in waitlist:
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
                    waitlist_count += 1
                except Exception:
                    pass

                # ↓ここから追加（メール通知）
                try:
                    waitlist_user = db.execute(
                        text("SELECT email, nickname FROM users WHERE id = :uid"),
                        {"uid": w.user_id}
                    ).fetchone()
                    if waitlist_user and waitlist_user.email:
                        import asyncio
                        from ..utils.email import send_email, meetup_waitlist_notification_html
                        asyncio.create_task(send_email(
                            to=waitlist_user.email,
                            subject="【推し道】MEETUPにキャンセルが出ました！",
                            html=meetup_waitlist_notification_html(
                                waitlist_user.nickname or "",
                                f"MEETUP (ID: {post_id})",
                            ),
                        ))
                except Exception as e:
                    print(f"メール送信エラー: {e}")

    db.commit()

    return {
        "status":             "cancelled",
        "cancel_fee":         cancel_fee,
        "is_chargeable":      is_chargeable,
        "waitlist_notified":  waitlist_count,
    }


# -------------------------------------------------------
# M-3b. 主催者キャンセル（期限チェック付き）
# -------------------------------------------------------
@router.post("/stripe/meetup-organizer-cancel")
async def meetup_organizer_cancel(data: dict, db: Session = Depends(get_db)):
    """
    主催者がMEETUP自体をキャンセルするとき。
    ✅ 開催24時間前より前 → キャンセル可能（参加者全員に通知・返金）
    ✅ 開催24時間前以降  → キャンセル不可（エラーを返す）
    """
    post_id      = data.get("postId")
    organizer_id = data.get("organizerId")
    if not post_id or not organizer_id:
        raise HTTPException(status_code=400, detail="postId と organizerId が必要です")

    post_id      = int(post_id)
    organizer_id = int(organizer_id)

    post = db.execute(
        text("SELECT user_id, meetup_date, meetup_fee_info, meetup_status FROM hobby_posts WHERE id = :pid"),
        {"pid": post_id}
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.user_id != organizer_id:
        raise HTTPException(status_code=403, detail="主催者のみ操作できます")
    if post.meetup_status == "cancelled":
        raise HTTPException(status_code=400, detail="既にキャンセル済みです")

    now = datetime.now(timezone.utc)

    # ✅ 開催24時間前チェック
    if post.meetup_date:
        meetup_dt = post.meetup_date
        if meetup_dt.tzinfo is None:
            meetup_dt = meetup_dt.replace(tzinfo=timezone.utc)

        cancel_deadline = meetup_dt - timedelta(hours=MEETUP_ORGANIZER_CANCEL_HOURS)

        if now >= cancel_deadline:
            # 24時間前を過ぎている → 主催者キャンセル不可
            hours_left = int((meetup_dt - now).total_seconds() / 3600)
            raise HTTPException(
                status_code=400,
                detail=f"開催{MEETUP_ORGANIZER_CANCEL_HOURS}時間前を過ぎているためキャンセルできません。"
                       f"（開催まで残り{hours_left}時間）"
            )

    # 参加者を全員取得
    participants = db.execute(text("""
        SELECT pr.user_id, pr.stripe_customer_id, pr.cancel_charged_at
        FROM post_responses pr
        WHERE pr.post_id = :pid AND pr.is_participation = true
    """), {"pid": post_id}).fetchall()

    refunded = []

    for p in participants:
        # 既に課金済みの参加者には返金
        if p.cancel_charged_at and p.stripe_customer_id:
            try:
                pis = stripe.PaymentIntent.list(customer=p.stripe_customer_id, limit=5)
                for pi in pis.data:
                    if (pi.metadata.get("post_id") == str(post_id)
                            and pi.metadata.get("product") == "meetup_fee"
                            and pi.status == "succeeded"):
                        stripe.Refund.create(payment_intent=pi.id)
                        refunded.append(p.user_id)
                        break
            except stripe.error.StripeError:
                pass

        # 通知送信
        post_info = db.execute(
            text("SELECT hobby_category_id FROM hobby_posts WHERE id = :pid"),
            {"pid": post_id}
        ).fetchone()
        try:
            db.execute(text("""
                INSERT INTO notifications
                    (recipient_id, sender_id, hobby_category_id, message, event_post_id, is_read)
                VALUES (:recipient, :sender, :cat_id, :msg, :post_id, false)
            """), {
                "recipient": p.user_id,
                "sender":    organizer_id,
                "cat_id":    post_info.hobby_category_id,
                "msg":       "主催者によりMEETUPがキャンセルされました。",
                "post_id":   post_id,
            })
        except Exception:
            pass

    # MEETUP自体をキャンセル状態に
    db.execute(text("""
        UPDATE hobby_posts
        SET meetup_status = 'cancelled', is_hidden = false
        WHERE id = :pid
    """), {"pid": post_id})
    db.commit()

    return {
        "status":   "organizer_cancelled",
        "refunded": len(refunded),
        "notified": len(participants),
    }


# -------------------------------------------------------
# M-4. No Show マーク
# -------------------------------------------------------
@router.post("/stripe/meetup-noshow")
async def meetup_noshow(data: dict, db: Session = Depends(get_db)):
    post_id   = data.get("postId")
    user_id   = data.get("userId")
    target_id = data.get("targetId")
    ntype     = data.get("type", "organizer")

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
            pms = stripe.PaymentMethod.list(customer=response.stripe_customer_id, type="card")
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

    elif ntype == "participant":
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
                pis = stripe.PaymentIntent.list(customer=p.stripe_customer_id, limit=5)
                for pi in pis.data:
                    if (pi.metadata.get("post_id") == str(post_id)
                            and pi.metadata.get("product") == "meetup_fee"
                            and pi.status == "succeeded"):
                        stripe.Refund.create(payment_intent=pi.id)
                        refunded.append(p.user_id)
                        break
            except stripe.error.StripeError:
                pass

        db.execute(text("""
            UPDATE hobby_posts SET meetup_organizer_showed = false WHERE id = :pid
        """), {"pid": post_id})
        db.commit()

        return {
            "status":   "organizer_noshow_reported",
            "refunded": len(refunded),
            "user_ids": refunded,
        }

    raise HTTPException(status_code=400, detail="type は 'organizer' か 'participant' を指定してください")


# -------------------------------------------------------
# 10. Stripe Webhook
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

    if event_type == "checkout.session.completed":
        product = stripe_session_obj.get("metadata", {}).get("product", "")
        user_id = stripe_session_obj.get("metadata", {}).get("user_id")

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
# -------------------------------------------------------
@router.get("/stripe/billing-summary")
async def get_billing_summary(user_id: int, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

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
        pass

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
        pass

    hide_affiliate_active = False
    try:
        ha_row = db.execute(text("""
            SELECT is_active FROM hide_affiliate_subscriptions
            WHERE user_id = :uid AND is_active = true
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        hide_affiliate_active = ha_row is not None
    except Exception:
        pass

    return {
        "friend_manager":    friend_manager,
        "hide_affiliate":    hide_affiliate_active,
        "one_time_payments": one_time,
    }


# -------------------------------------------------------
# Stripe Connect：主催者オンボーディング
# -------------------------------------------------------

@router.post("/stripe/connect/onboard")
async def create_connect_onboard(data: dict, db: Session = Depends(get_db)):
    """
    主催者がStripe Connectアカウントを作成してオンボーディングするURL発行。
    """
    user_id = data.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId が必要です")
    
    user_id = int(user_id)
    
    # ユーザー情報取得
    user = db.execute(
        text("SELECT id, email, nickname, stripe_connect_account_id FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    # すでにConnectアカウントがあればそれを使う
    connect_account_id = user.stripe_connect_account_id

    if not connect_account_id:
        # 新規Expressアカウント作成
        account = stripe.Account.create(
            type="express",
            country="JP",
            email=user.email,
            capabilities={
                "transfers": {"requested": True},
            },
            # ここから下が追加・修正ポイントです
            business_type="individual",  # 最初から「個人事業主」を選択状態にする
            business_profile={
                "url": "https://osidou.com",  # osidouのURLをセット
                "mcc": "5734",  # 業種：コンピュータソフトウェアサービスを指定
                "product_description": "osidou（推し道）プラットフォームを通じたコミュニティ運営・MEETUPイベントの参加費受領のため。",
            },
            metadata={"user_id": str(user_id)},
        )
        connect_account_id = account.id

        # DBに保存
        db.execute(text("""
            UPDATE users 
            SET stripe_connect_account_id = :acct_id
            WHERE id = :uid
        """), {"acct_id": connect_account_id, "uid": user_id})
        db.commit()

    # オンボーディングURL発行
    try:
        account_link = stripe.AccountLink.create(
            account=connect_account_id,
            refresh_url=f"{FRONTEND_URL}/profile?connect_refresh=true",
            return_url=f"{FRONTEND_URL}/profile?connect_done=true",
            type="account_onboarding",
        )
        return {"url": account_link.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe エラー: {str(e)}")


@router.get("/stripe/connect/status")
async def get_connect_status(user_id: int, db: Session = Depends(get_db)):
    """
    主催者のConnect状態を確認する。
    """
    user = db.execute(
        text("SELECT stripe_connect_account_id, stripe_connect_onboarded FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    
    if not user or not user.stripe_connect_account_id:
        return {"connected": False}

    # Stripeから最新状態を確認
    try:
        account = stripe.Account.retrieve(user.stripe_connect_account_id)
        is_ready = (
            account.charges_enabled and 
            account.payouts_enabled and
            account.details_submitted
        )
        
        # DBのステータスも更新
        if is_ready and not user.stripe_connect_onboarded:
            db.execute(text("""
                UPDATE users SET stripe_connect_onboarded = true WHERE id = :uid
            """), {"uid": user_id})
            db.commit()
        
        return {
            "connected": True,
            "account_id": user.stripe_connect_account_id,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "is_ready": is_ready,
        }
    except stripe.error.StripeError:
        return {"connected": False}