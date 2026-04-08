from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings


def send_email(settings: Settings, to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password or not settings.smtp_from:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return True

