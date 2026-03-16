import csv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import stripe
import io
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db

router = APIRouter(prefix="/api", tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/stripe/feeling-log-checkout")
async def create_checkout_session(data: dict):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'jpy',
                    'product_data': {'name': 'Feeling Log ダウンロード'},
                    'unit_amount': 200,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=data['successUrl'],
            cancel_url=data['cancelUrl'],
            metadata={'user_id': data['userId']}
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/feeling-log")
async def download_feeling_log(session_id: str, db: Session = Depends(get_db)):
    # 1. Stripe Sessionの検証
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != 'paid':
            raise HTTPException(status_code=403, detail="決済が完了していません")
    except Exception as e:
        raise HTTPException(status_code=400, detail="無効なセッションです")

    user_id = session.metadata.get('user_id')
    
    # 2. DBからログを取得（最大1000件、直近3ヶ月）
    # ※テーブル名やカラム名は環境に合わせて調整してください
    # stripe_payment.py 内のクエリを以下に合わせる
    query = text("""
        SELECT created_at, mood_type, comment
        FROM mood_logs
        WHERE user_id = :user_id
        AND is_visible = true
        AND created_at > NOW() - INTERVAL '3 months'
        ORDER BY created_at DESC
        LIMIT 1000
    """)
    
    # パラメータ名も user_id に合わせると分かりやすいです
    result = db.execute(query, {"user_id": profile_id})
    logs = result.fetchall()

    # 3. CSV生成 (メモリ上のバッファに書き込み)
    output = io.StringIO()

    # Excelで開いた時に文字化けしないようBOM(UTF-8)を付与
    output.write('\ufeff')

    writer = csv.writer(output)

    # ヘッダー
    writer.writerow(["date", "time", "mood", "emoji", "comment"])

    # 絵文字マップ
    MOOD_EMOJI = {
        "happy": "😊",
        "excited": "🤩",
        "calm": "😌",
        "tired": "😥",
        "sad": "😭",
        "anxious": "😟",
        "angry": "😠",
        "neutral": "😐",
        "grateful": "🙏",
        "motivated": "🔥"
    }

    # データ行
    for log in logs:
        dt = log.created_at

        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M')

        writer.writerow([
            date_str,
            time_str,
            log.mood_type,
            MOOD_EMOJI.get(str(log.mood_type), ""),
            log.comment or ""
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=feeling_log.csv"
        }
    )