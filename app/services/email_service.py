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

    subject = "ClipForgeReels: Password Reset Verification Code"
    
    # Plain text fallback
    text_body = f"""Hello,
    
We received a request to reset your password. 
Your 6-digit verification code is: {otp}

This code will expire in 15 minutes. If you did not request this, please ignore this email.

Thanks,
ClipForgeReels Team
"""

    # HTML structure
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f4f7f6;
                margin: 0;
                padding: 0;
                color: #333333;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #4F46E5;
                color: #ffffff;
                padding: 30px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            .otp-box {{
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 20px;
                text-align: center;
                margin: 30px 0;
            }}
            .otp-code {{
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 4px;
                color: #4F46E5;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 20px;
                text-align: center;
                border-top: 1px solid #e2e8f0;
            }}
            .footer p {{
                font-size: 14px;
                color: #64748b;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ClipForgeReels</h1>
            </div>
            <div class="content">
                <p>We received a request to reset your password. Please use the verification code below to complete the process:</p>
                
                <div class="otp-box">
                    <div class="otp-code">{otp}</div>
                </div>
                
                <p><strong>Note:</strong> This code will expire in 15 minutes. If you did not request a password reset, you can safely ignore this email.</p>
                
                <p>Thanks,<br>The ClipForgeReels Team</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 ClipForgeReels. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    
    # Set the text version first
    msg.set_content(text_body)
    # Then add the HTML version as an alternative
    msg.add_alternative(html_body, subtype='html')

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

def send_support_email(fullname: str, user_email: str, subject: str, topic: str, message: str):
    """
    Sends a support inquiry email.
    """
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print(f"SMTP Configuration missing! Unable to send support email from {user_email}")
        return False

    body = f"""Support Inquiry Received:

Name: {fullname}
Email: {user_email}
Topic: {topic}

Message:
{message}
"""

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = f"Support Request: {subject}"
    # Send from the app's configured email
    msg["From"] = settings.SMTP_USERNAME
    # Send to the app's configured email or a dedicated support email
    msg["To"] = settings.SMTP_USERNAME
    # Reply-to the user who submitted the request
    msg["Reply-To"] = user_email

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Successfully sent support email for {user_email}")
            return True
    except Exception as e:
        print(f"Failed to send support email for {user_email}: {e}")
        return False


def send_welcome_email(to_email: str, name: str):
    """
    Sends a welcome email to the newly registered/verified user.
    """
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print(f"SMTP Configuration missing! Unable to send welcome email to {to_email}")
        return False

    subject = "Welcome to ClipForgeReels!"
    
    text_body = f"""Welcome to ClipForgeReels, {name}!
    
We are thrilled to have you join us. ClipForgeReels is designed to help you create stunning, high-quality video content, reels, and subtitles in just a few clicks using advanced generative AI.

Here is what you can do to get started:
1. Generate Videos from Prompts: Bring your ideas to life with text-to-video AI.
2. Professional Voices: Choose from realistic AI voiceovers to narrate your content.
3. Custom Subtitles: Add beautifully animated subtitles in various influencer styles.

Your account has been credited with free credits to get you started immediately.

Start creating now: www.clipforgereels.com

If you have any questions, reply to this email or contact support.

Happy creating,
The ClipForgeReels Team
"""

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome to ClipForgeReels</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f4f7f6;
                margin: 0;
                padding: 0;
                color: #333333;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}
            .header {{
                background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
                color: #ffffff;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .content h2 {{
                font-size: 20px;
                color: #1e293b;
                margin-top: 0;
                margin-bottom: 15px;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.6;
                color: #475569;
                margin-bottom: 20px;
            }}
            .features {{
                margin: 30px 0;
                padding: 0;
                list-style-type: none;
            }}
            .feature-item {{
                display: flex;
                align-items: flex-start;
                margin-bottom: 15px;
            }}
            .feature-icon {{
                font-size: 20px;
                margin-right: 12px;
                margin-top: 2px;
            }}
            .feature-text {{
                font-size: 15px;
                color: #475569;
                line-height: 1.5;
            }}
            .cta-box {{
                text-align: center;
                margin: 35px 0 20px 0;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #4F46E5;
                color: #ffffff;
                text-decoration: none;
                padding: 14px 30px;
                font-size: 16px;
                font-weight: 600;
                border-radius: 6px;
                box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 25px;
                text-align: center;
                border-top: 1px solid #e2e8f0;
            }}
            .footer p {{
                font-size: 13px;
                color: #94a3b8;
                margin: 0;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to ClipForgeReels!</h1>
            </div>
            <div class="content">
                <h2>Hi {name},</h2>
                <p>We're thrilled to have you join us! ClipForgeReels is designed to help you create stunning, high-quality video content, reels, and subtitles in just a few clicks using advanced generative AI.</p>
                <p>Here are a few things you can do to get started:</p>
                
                <ul class="features">
                    <li class="feature-item">
                        <span class="feature-icon">✨</span>
                        <div class="feature-text"><strong>Generate Videos from Prompts:</strong> Bring your ideas to life with text-to-video AI.</div>
                    </li>
                    <li class="feature-item">
                        <span class="feature-icon">🎙️</span>
                        <div class="feature-text"><strong>Professional Voices:</strong> Choose from realistic AI voiceovers to narrate your content.</div>
                    </li>
                    <li class="feature-item">
                        <span class="feature-icon">📝</span>
                        <div class="feature-text"><strong>Custom Subtitles:</strong> Add beautifully animated subtitles in various influencer styles.</div>
                    </li>
                </ul>

                <p>Your account is already credited with free credits to get you started immediately.</p>
                
                <div class="cta-box">
                    <a href="www.clipforgereels.com" class="cta-button" style="color: #ffffff;">Start Creating Now</a>
                </div>
                
                <p>If you have any questions or need help, feel free to reply to this email or reach out to our support team.</p>
                
                <p>Happy creating,<br>The ClipForgeReels Team</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 ClipForgeReels. All rights reserved.<br>You received this email because you signed up for ClipForgeReels.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    
    # Set the text version first
    msg.set_content(text_body)
    # Then add the HTML version as an alternative
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Successfully sent welcome email to {to_email}")
            return True
    except Exception as e:
        print(f"Failed to send welcome email to {to_email}: {e}")
        return False


