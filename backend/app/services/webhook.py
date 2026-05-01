# backend/app/services/webhook.py
import smtplib
import structlog
from email.message import EmailMessage
from app.config import get_settings
from app.models.schemas import TripPlan

settings = get_settings()
log = structlog.get_logger()


def send_webhook_sync(payload: TripPlan):
    """Synchronous version – runs safely in a background thread."""
    try:
        msg = EmailMessage()
        msg["From"] = settings.webhook_gmail_address
        msg["To"] = payload.user_email
        msg["Subject"] = f"Your trip plan: {payload.query[:50].strip()}..."

        body = f"""Hi there!

Here is the trip plan you requested:

{payload.plan}

---
Sent by Smart Travel Planner
Query: {payload.query}
"""
        msg.set_content(body)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(
                settings.webhook_gmail_address,
                settings.webhook_gmail_app_password,
            )
            server.send_message(msg)

        log.info("email.sent", to=payload.user_email)
    except Exception as e:
        log.error("email.failed", error=str(e))