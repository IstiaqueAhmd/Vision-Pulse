import smtplib
from email.message import EmailMessage
from app.core.config import settings

def send_otp_email(to_email: str, otp: str):
    """
    Sends an OTP to the given email address using standard SMTP.
    """
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print(f"SMTP Configuration missing! Falling back to MOCK OTP: {otp}")
        return

    subject = "Vision-Pulse: Password Reset Verification Code"
    body = f"""Hello,
    
We received a request to reset your password. 
Your 6-digit verification code is: {otp}

This code will expire in 15 minutes. If you did not request this, please ignore this email.

Thanks,
Vision-Pulse Team
"""

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email

    try:
        # We assume STARTTLS (Port 587) which is standard for Gmail and most providers
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Successfully sent OTP to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # Depending on requirements, we could raise an HTTPException here, 
        # but often it's safer to fail silently and log it so we don't leak failures to the client.
