from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
import re

# Schema for user registration
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2)

    # Password validation
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) > 72:
            raise ValueError('Password cannot be longer than 72 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain digit')
        return v

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
    # Configuration to work with ORM models
    class Config:
        from_attributes = True