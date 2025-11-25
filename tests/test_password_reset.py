import pytest
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.services import password_reset_service
from app.utils.security import hash_password, verify_password


def create_user(session, email="user@example.com", password="Password123!", name="Test User"):
    user = User(email=email, password_hash=hash_password(password), name=name)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def capture_reset_email(monkeypatch):
    captured = {}

    def fake_send(cls, recipient, reset_link):
        captured["recipient"] = recipient
        captured["link"] = reset_link

    monkeypatch.setattr(
        password_reset_service.EmailService,
        "send_password_reset_email",
        classmethod(fake_send),
    )
    return captured


def test_forgot_password_creates_token_and_sends_email(client, db_session, monkeypatch):
    user = create_user(db_session)
    captured = capture_reset_email(monkeypatch)
    monkeypatch.setattr(password_reset_service, "PASSWORD_RESET_URL", "http://frontend/reset-password")

    response = client.post("/api/auth/forgot-password", json={"email": user.email})

    assert response.status_code == 202
    assert captured["recipient"] == user.email
    assert captured["link"].startswith("http://frontend/reset-password/")

    db_session.expire_all()
    tokens = db_session.query(PasswordResetToken).all()
    assert len(tokens) == 1
    assert tokens[0].user_id == user.id
    assert tokens[0].used_at is None


def test_full_reset_flow_updates_password_and_consumes_token(client, db_session, monkeypatch):
    user = create_user(db_session, password="OldPass123!")
    captured = capture_reset_email(monkeypatch)
    monkeypatch.setattr(password_reset_service, "PASSWORD_RESET_URL", "http://frontend/reset-password")

    # Request reset to generate token
    response = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 202
    raw_token = captured["link"].rstrip("/").split("/")[-1]

    # Complete reset with captured token
    reset_payload = {
        "token": raw_token,
        "new_password": "NewPass123!",
        "confirm_password": "NewPass123!",
    }
    reset_response = client.post("/api/auth/reset-password", json=reset_payload)

    assert reset_response.status_code == 200
    db_session.expire_all()

    updated_user = db_session.get(User, user.id)
    assert verify_password("NewPass123!", updated_user.password_hash)

    tokens = db_session.query(PasswordResetToken).all()
    assert len(tokens) == 1
    assert tokens[0].used_at is not None


def test_reset_password_with_invalid_token_fails(client, db_session):
    user = create_user(db_session, password="KeepPass123!")

    payload = {
        "token": "x" * 48,
        "new_password": "AnotherPass123!",
        "confirm_password": "AnotherPass123!",
    }
    response = client.post("/api/auth/reset-password", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token."

    db_session.expire_all()
    fresh_user = db_session.get(User, user.id)
    assert verify_password("KeepPass123!", fresh_user.password_hash)

