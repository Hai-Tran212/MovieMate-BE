"""
Create password_reset_tokens table separately from other migrations.
Run with: python -m app.migrations.create_password_reset_tokens_table
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import engine  # noqa: E402
from app.models.password_reset_token import PasswordResetToken  # noqa: E402


def create_password_reset_tokens_table():
    """Create the password_reset_tokens table if it does not exist."""
    print("=" * 60)
    print("Creating password_reset_tokens table...")
    print("=" * 60)

    try:
        PasswordResetToken.__table__.create(bind=engine, checkfirst=True)
        print("✅ password_reset_tokens table is ready.")
    except Exception as exc:  # pragma: no cover - only hit on migration failures
        print(f"❌ Failed to create password_reset_tokens table: {exc}")
        raise


if __name__ == "__main__":
    create_password_reset_tokens_table()

