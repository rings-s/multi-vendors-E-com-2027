"""Transactional email. Sends via SMTP when configured, otherwise only logs."""

import smtplib
from email.message import EmailMessage

import structlog
from asyncer import asyncify

from app.core.config import get_settings

log = structlog.get_logger(__name__)


def _send_smtp(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    assert settings.smtp_host is not None
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        log.info("email_not_configured", to=to, subject=subject)
        return False
    try:
        await asyncify(_send_smtp)(to, subject, body)
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("email_send_failed", to=to, error=str(exc))
        return False
    return True
