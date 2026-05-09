from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MailerNotConfiguredError(RuntimeError):
    pass


def is_mailer_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


async def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    if not is_mailer_configured():
        raise MailerNotConfiguredError("SMTP no configurado")

    message = EmailMessage()
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        if settings.smtp_from_name
        else settings.smtp_from_email
    )
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    await asyncio.to_thread(_deliver, message)
    logger.info("[Mail] sent to=%s subject=%s", to_email, subject)


def _deliver(message: EmailMessage) -> None:
    if settings.smtp_use_ssl:
        server = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )
    else:
        server = smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )

    try:
        server.ehlo()
        if settings.smtp_use_starttls and not settings.smtp_use_ssl:
            server.starttls()
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()
