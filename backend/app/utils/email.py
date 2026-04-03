import os
import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = "system@osidou.com"

async def send_email(to: str, subject: str, html: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": FROM_EMAIL, "to": to, "subject": subject, "html": html},
        )