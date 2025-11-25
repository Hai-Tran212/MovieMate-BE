from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.utils.dependencies import get_current_user
from app.models.user import User

# Define router
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Register a new user
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    user = AuthService.register_user(db, user_data)
    return user

# Login endpoint
@router.post("/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login with email and password"""
    return AuthService.login_user(db, credentials)

# Get current authenticated user
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user"""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request a password reset link."""
    client_ip = request.client.host if request.client else None
    PasswordResetService.request_reset(db, payload.email, client_ip)
    return {"message": "If an account exists for that email, we sent reset instructions."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Complete password reset with a valid token."""
    PasswordResetService.reset_password(db, payload.token, payload.new_password)
    return {"message": "Password reset successful. You can now log in with your new password."}