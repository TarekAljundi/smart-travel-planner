import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import smtplib
from email.message import EmailMessage
from app.config import get_settings

settings = get_settings()

msg = EmailMessage()
msg["From"] = settings.webhook_gmail_address
msg["To"] = settings.webhook_gmail_address   # send to yourself
msg["Subject"] = "Test Email from Smart Travel Planner"
msg.set_content("If you see this, the email setup works!")

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(settings.webhook_gmail_address, settings.webhook_gmail_app_password)
        server.send_message(msg)
    print("✅ Email sent successfully! Check your inbox/spam.")
except Exception as e:
    print(f"❌ Failed to send email: {e}")