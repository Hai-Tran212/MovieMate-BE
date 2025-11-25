import logging
import os
import smtplib
from email.message import EmailMessage
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class EmailService:
    """Simple SMTP-based email sender."""

    @staticmethod
    def _get_config() -> dict:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USERNAME")
        password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("EMAIL_FROM")
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

        if not host or not from_email:
            logger.error("SMTP_HOST and EMAIL_FROM must be configured for email sending")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email service is not configured",
            )

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "from_email": from_email,
            "use_tls": use_tls,
        }

    @classmethod
    def send_password_reset_email(cls, recipient: str, reset_link: str) -> None:
        """Send password reset instructions to the specified recipient."""
        subject = "Reset your MovieMate password"
        body = (
            "Hi there,\n\n"
            "We received a request to reset the password for your MovieMate account.\n"
            "If you made this request, click the link below to choose a new password:\n\n"
            f"{reset_link}\n\n"
            "If you did not request a password reset, you can safely ignore this email.\n\n"
            "— The MovieMate Team"
        )
        cls._send_email(recipient, subject, body)

    @classmethod
    def _send_email(cls, recipient: str, subject: str, body: str) -> None:
        config = cls._get_config()

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config["from_email"]
        message["To"] = recipient
        message.set_content(body)

        try:
            with smtplib.SMTP(config["host"], config["port"]) as server:
                server.ehlo()
                if config["use_tls"]:
                    server.starttls()
                    server.ehlo()
                if config["username"] and config["password"]:
                    server.login(config["username"], config["password"])
                server.send_message(message)
        except Exception as exc:  # pragma: no cover - network failures are runtime concerns
            logger.exception("Failed to send email via SMTP: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to send email at this time",
            )

