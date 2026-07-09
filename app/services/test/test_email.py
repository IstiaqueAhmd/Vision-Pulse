import os
import sys

# Ensure the root directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.core.config import settings
from app.services.email_service import send_otp_email, send_support_email, send_welcome_email

def test_emails():
    print("==================================================")
    print("          Vision-Pulse Email Test Script          ")
    print("==================================================")
    
    # 1. Print SMTP configuration (masked)
    print("\n[1] Checking SMTP Settings:")
    print(f"  SMTP Server:    {settings.SMTP_SERVER}")
    print(f"  SMTP Port:      {settings.SMTP_PORT}")
    print(f"  SMTP From:      {settings.SMTP_FROM_EMAIL}")
    print(f"  SMTP Username:  {settings.SMTP_USERNAME}")
    has_pwd = "Configured" if settings.SMTP_PASSWORD else "Missing"
    print(f"  SMTP Password:  {has_pwd}")
    
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print("\n[!] WARNING: SMTP_USERNAME or SMTP_PASSWORD is not configured.")
        print("    Emails will fall back to local console mock prints.")
    
    # 2. Get target email address
    target_email = ""
    if len(sys.argv) > 1:
        target_email = sys.argv[1]
    else:
        try:
            target_email = input("\nEnter target email address to send test emails to: ").strip()
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)
            
    if not target_email:
        print("Error: Target email address is required.")
        sys.exit(1)
        
    print(f"\nSending test emails to: {target_email}\n")
    
    # 3. Test send_otp_email
    print("--------------------------------------------------")
    print("Testing send_otp_email...")
    try:
        send_otp_email(to_email=target_email, otp="123456")
        print("✔ send_otp_email execution completed.")
    except Exception as e:
        print(f"✘ send_otp_email failed: {e}")
        
    # 4. Test send_welcome_email
    print("\nTesting send_welcome_email...")
    try:
        send_welcome_email(to_email=target_email, name="Test User")
        print("✔ send_welcome_email execution completed.")
    except Exception as e:
        print(f"✘ send_welcome_email failed: {e}")

    # 5. Test send_support_email
    print("\nTesting send_support_email...")
    try:
        success = send_support_email(
            fullname="Test Sender",
            user_email=target_email,
            subject="Test Support Request",
            topic="General Inquiry",
            message="This is a test message from the Vision-Pulse test script."
        )
        if success:
            print(f"✔ send_support_email completed successfully. (It was sent to the support address: {settings.SMTP_USERNAME})")
        else:
            print("✘ send_support_email returned False (SMTP missing or error).")
    except Exception as e:
        print(f"✘ send_support_email failed: {e}")

    print("\n==================================================")
    print("                  Testing Finished                ")
    print("==================================================")

if __name__ == "__main__":
    test_emails()
