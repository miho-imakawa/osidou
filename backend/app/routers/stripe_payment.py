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

    # すでに有効な購入があれば Stripe に飛ばさずそのまま返す
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
# 3. Friends' Feeling Log 購入アクティベート（Stripe成功後）
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

    # 重複チェック（同じセッションIDで二重登録しない）
    already = db.execute(text("""
        SELECT id FROM friends_log_purchases WHERE stripe_session_id = :sid
    """), {"sid": session_id}).fetchone()

    if already:
        # すでに登録済み → 現在の状態を返すだけ
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

    # 今日すでにDL済みか確認
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
    # 有効な購入チェック
    purchase = db.execute(text("""
        SELECT id FROM friends_log_purchases
        WHERE buyer_user_id = :uid
          AND is_active = true
          AND expires_at > NOW()
        LIMIT 1
    """), {"uid": user_id}).fetchone()

    if not purchase:
        raise HTTPException(status_code=403, detail="有効な購入がありません")

    # 1日1回制限チェック
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

    # 友達全員の最新ログ取得（直近30日）
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
            -- フレンド関係のuser_idを取得
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

    # DL記録を保存
    db.execute(text("""
        INSERT INTO friends_log_downloads (buyer_user_id, download_date)
        VALUES (:uid, CURRENT_DATE)
        ON CONFLICT (buyer_user_id, download_date) DO NOTHING
    """), {"uid": user_id})
    db.commit()

    # CSV生成
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

    if event["type"] == "checkout.session.completed":
        stripe_session = event["data"]["object"]
        product = stripe_session.get("metadata", {}).get("product", "")
        user_id = stripe_session.get("metadata", {}).get("user_id")

        # Friends' Log は Webhook 側でも自動アクティベート
        if product == "friends_log" and user_id:
            already = db.execute(text(
                "SELECT id FROM friends_log_purchases WHERE stripe_session_id = :sid"
            ), {"sid": stripe_session["id"]}).fetchone()

            if not already:
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                try:
                    db.execute(text("""
                        INSERT INTO friends_log_purchases
                            (buyer_user_id, stripe_session_id, purchased_at, expires_at, is_active)
                        VALUES (:uid, :sid, NOW(), :expires, true)
                    """), {
                        "uid": int(user_id),
                        "sid": stripe_session["id"],
                        "expires": expires_at,
                    })
                    db.commit()
                except Exception:
                    db.rollback()

        # 支払い記録
        try:
            db.execute(text("""
                INSERT INTO stripe_payments (session_id, user_id, product, amount, paid_at)
                VALUES (:session_id, :user_id, :product, :amount, NOW())
                ON CONFLICT (session_id) DO NOTHING
            """), {
                "session_id": stripe_session["id"],
                "user_id": user_id,
                "product": product,
                "amount": stripe_session.get("amount_total", 0),
            })
            db.commit()
        except Exception:
            db.rollback()

    return {"status": "ok"}
