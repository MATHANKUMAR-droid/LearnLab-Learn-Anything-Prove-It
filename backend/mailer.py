"""
mailer.py
Sends real email OTPs via SMTP if credentials are configured through
environment variables. Falls back to printing the OTP to the server console
(and returning it in the API response marked as "dev mode") so the app is
fully runnable without any email setup out of the box.

To send real emails, set:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@gmail.com
    SMTP_PASS=your-app-password       (Gmail: use an "App Password", not your login password)
    SMTP_FROM=you@gmail.com
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


def smtp_configured() -> bool:
    return all([SMTP_HOST, SMTP_USER, SMTP_PASS])


def send_otp_email(to_email: str, otp_code: str, purpose: str = "sign up"):
    """Returns dict: {sent: bool, dev_mode: bool, otp_code: str (only if dev_mode)}"""
    subject = f"Your LearnLab verification code: {otp_code}"
    body = (
        f"Hi,\n\nYour one-time verification code to {purpose} on LearnLab is:\n\n"
        f"    {otp_code}\n\n"
        f"This code expires in 10 minutes. If you didn't request this, you can ignore this email.\n\n"
        f"— LearnLab"
    )

    if not smtp_configured():
        # Dev fallback: no SMTP configured, so we can't actually deliver email.
        print(f"[DEV MODE] OTP for {to_email} ({purpose}): {otp_code}")
        return {"sent": False, "dev_mode": True, "otp_code": otp_code}

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return {"sent": True, "dev_mode": False}
    except Exception as e:
        print(f"[MAILER ERROR] Falling back to dev mode: {e}")
        return {"sent": False, "dev_mode": True, "otp_code": otp_code, "error": str(e)}
