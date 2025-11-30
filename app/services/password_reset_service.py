import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email_service import EmailService
from app.utils.security import hash_password

RESET_TOKEN_TTL_MINUTES = int(os.getenv("RESET_TOKEN_TTL_MINUTES", "30"))
RESET_TOKEN_MAX_ACTIVE = int(os.getenv("RESET_TOKEN_MAX_ACTIVE", "3"))
PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", "http://localhost:5173/reset-password")


class PasswordResetService:
    """Handles password reset token issuance and validation."""

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _cleanup_expired_tokens(db: Session) -> None:
        now = PasswordResetService._utcnow()
        db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at <= now
        ).delete(synchronize_session=False)

    @staticmethod
    def _build_reset_link(raw_token: str) -> str:
        base = PASSWORD_RESET_URL.rstrip("/")
        return f"{base}/{raw_token}"

    @classmethod
    def request_reset(cls, db: Session, email: str, client_ip: Optional[str] = None) -> None:
        user = db.query(User).filter(User.email == email).first()

        # Always clean up expired tokens to keep table small
        cls._cleanup_expired_tokens(db)

        if not user:
            # Do not reveal whether an email exists
            db.commit()
            return

        active_tokens = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > cls._utcnow(),
            )
            .count()
        )

        if active_tokens >= RESET_TOKEN_MAX_ACTIVE:
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset requests. Please try again later.",
            )

        raw_token = secrets.token_urlsafe(48)
        now = cls._utcnow()
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=cls._hash_token(raw_token),
            expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
            requested_ip=client_ip,
        )
        db.add(token_record)

        reset_link = cls._build_reset_link(raw_token)

        try:
            EmailService.send_password_reset_email(user.email, reset_link)
        except Exception:
            db.rollback()
            raise
        else:
            db.commit()

    @classmethod
    def reset_password(cls, db: Session, token: str, new_password: str) -> None:
        token_hash = cls._hash_token(token)
        reset_record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
            .first()
        )

        now = cls._utcnow()
        if (
            reset_record is None
            or cls._ensure_aware(reset_record.expires_at) < now
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        user = db.query(User).filter(User.id == reset_record.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        user.password_hash = hash_password(new_password)
        reset_record.used_at = now

        # Invalidate any other outstanding tokens for this user
        invalidate_time = cls._utcnow()
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.id != reset_record.id,
        ).update(
            {"used_at": invalidate_time},
            synchronize_session=False,
        )

        db.commit()
