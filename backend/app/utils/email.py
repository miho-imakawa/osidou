import os
import httpx
from typing import Optional

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = "system@osidou.com"


async def send_email(to: str, subject: str, html: str) -> bool:
    """Resend APIでメールを送信する。失敗してもアプリを止めない。"""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY が設定されていません")
        return False
    if not to:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": FROM_EMAIL,
                    "to": to,
                    "subject": subject,
                    "html": html,
                },
            )
            if res.status_code >= 400:
                print(f"Resend エラー: {res.status_code} {res.text}")
                return False
            return True
    except Exception as e:
        print(f"メール送信例外: {e}")
        return False


# ─────────────────────────────────────────
# メールテンプレート
# ─────────────────────────────────────────

def welcome_email_html(nickname: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;">
      <h2 style="color:#FF4D8D;">推し道へようこそ！🎉</h2>
      <p>ようこそ {nickname} さん、この度は、ご登録いただきありがとうございます。</p>
      <p>好きなことを大切に。気持ちを記録する。<br>
         そこから、同じ「好き」を持つ仲間が見つかります。</p>
      <a href="https://osidou.com"
         style="display:inline-block;margin-top:16px;padding:12px 28px;
                background:#FF4D8D;color:#fff;border-radius:40px;
                text-decoration:none;font-weight:700;">
        さっそく"推し道"をはじめよう →
      </a>
      <p style="margin-top:32px;font-size:12px;color:#999;">
        ※ このメールは自動送信です。返信はできません。
      </p>
    </div>
    """

def meetup_waitlist_notification_html(nickname: str, meetup_title: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;">
      <h2 style="color:#FF4D8D;">キャンセルが出ました！</h2>
      <p>{nickname} さん、キャンセル待ちのMEETUPに空きが出ました。</p>
      <p style="font-weight:700;">{meetup_title}</p>
      <p>アプリから参加手続きをお早めに！<br>
         先着順のため、お急ぎください。</p>
      <a href="https://osidou.com"
         style="display:inline-block;margin-top:16px;padding:12px 28px;
                background:#FF4D8D;color:#fff;border-radius:40px;
                text-decoration:none;font-weight:700;">
        今すぐ確認する →
      </a>
      <p style="margin-top:32px;font-size:12px;color:#999;">
        ※ このメールは自動送信です。返信はできません。
      </p>
    </div>
    """