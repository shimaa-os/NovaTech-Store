import smtplib
from email.message import EmailMessage

from ..config import Settings


def send_otp_email(settings_payload: dict, recipient: str, otp: str) -> None:
    settings = Settings.model_validate(settings_payload)
    if not settings.smtp_host or not settings.email_from:
        if settings.environment == "production":
            raise RuntimeError("SMTP is not configured")
        print(f"NovaTech development OTP for {recipient}: {otp}")
        return
    message = EmailMessage()
    message["Subject"] = "NovaTech Store verification code"
    message["From"] = settings.email_from
    message["To"] = recipient
    message.set_content(f"Your NovaTech Store verification code is {otp}. It expires in 10 minutes.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as connection:
        if settings.smtp_starttls:
            connection.starttls()
        if settings.smtp_username:
            connection.login(settings.smtp_username, settings.smtp_password)
        connection.send_message(message)

