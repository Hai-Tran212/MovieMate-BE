from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin
from app.utils.security import hash_password, verify_password, create_access_token
from fastapi import HTTPException, status
from datetime import timedelta
import os
import logging
from typing import cast

logger = logging.getLogger(__name__)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

class AuthService:
    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        # Check existing email
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        # Validate password length for bcrypt (max 72 bytes)
        if len(user_data.password.encode('utf-8')) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Password cannot be longer than 72 characters"
            )

        # Create user
        new_user = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            name=user_data.name
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    

    @staticmethod
    def login_user(db: Session, credentials: UserLogin) -> dict:
        # Find user
        user = db.query(User).filter(User.email == credentials.email).first()
        
        # Debug logging
        if not user:
            logger.warning(f"Login failed: User not found with email {credentials.email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
        
        if not verify_password(credentials.password, str(user.password_hash)):
            logger.warning(f"Login failed: Incorrect password for email {credentials.email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
        # Cast is_active to bool to satisfy static type checking tools
        if not cast(bool, user.is_active):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated") 
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated") 

        # Create token
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user
        }