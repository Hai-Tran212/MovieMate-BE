from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict, ValidationInfo
from datetime import datetime
import re


def ensure_password_strength(password: str) -> str:
    """Validate password complexity requirements."""
    if len(password) > 72:
        raise ValueError('Password cannot be longer than 72 characters')
    if not re.search(r'[A-Z]', password):
        raise ValueError('Password must contain uppercase letter')
    if not re.search(r'[a-z]', password):
        raise ValueError('Password must contain lowercase letter')
    if not re.search(r'[0-9]', password):
        raise ValueError('Password must contain digit')
    return password


# Schema for user registration
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2)

    # Password validation
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        return ensure_password_strength(v)

# Schema for user login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Schema for user response
class UserResponse(BaseModel):  
    id: int
    email: str
    name: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=255)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        return ensure_password_strength(v)

    @field_validator('confirm_password')
    @classmethod
    def confirm_matches(cls, v, info: ValidationInfo):
        new_password = info.data.get('new_password')
        if new_password and v != new_password:
            raise ValueError('Passwords do not match')
        return v


class MessageResponse(BaseModel):
    message: str