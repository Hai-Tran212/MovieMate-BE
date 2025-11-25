from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    requested_ip = Column(String(45), nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")

    __table_args__ = (
        Index("ix_password_reset_tokens_user_id_expires", "user_id", "expires_at"),
    )