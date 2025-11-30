"""Input validation schemas with XSS protection"""

from pydantic import BaseModel, Field, field_validator
import re
import bleach

# Allowed HTML tags for user input
ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']


class SafeStringMixin:
    """Mixin for XSS-safe string validation"""
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """Remove dangerous HTML/JavaScript"""
        if not value:
            return value
        return bleach.clean(value, tags=ALLOWED_TAGS, strip=True)
    
    @staticmethod
    def validate_no_script(value: str) -> str:
        """Block common XSS patterns"""
        if not value:
            return value
        
        dangerous_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError("Invalid characters detected")
        
        return value


class SearchQuerySchema(BaseModel, SafeStringMixin):
    """Validated search query"""
    query: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('query')
    @classmethod
    def clean_query(cls, v):
        return cls.validate_no_script(v)


class ReviewSchema(BaseModel, SafeStringMixin):
    """Validated review input (future feature)"""
    content: str = Field(..., min_length=10, max_length=2000)
    
    @field_validator('content')
    @classmethod
    def clean_content(cls, v):
        v = cls.validate_no_script(v)
        return cls.sanitize_html(v)


class CommentSchema(BaseModel, SafeStringMixin):
    """Validated comment input (future feature)"""
    text: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('text')
    @classmethod
    def clean_text(cls, v):
        v = cls.validate_no_script(v)
        return cls.sanitize_html(v)


class UsernameSchema(BaseModel):
    """Validated username"""
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')


class BioSchema(BaseModel, SafeStringMixin):
    """Validated bio (future feature)"""
    bio: str = Field(..., max_length=500)
    
    @field_validator('bio')
    @classmethod
    def clean_bio(cls, v):
        v = cls.validate_no_script(v)
        return cls.sanitize_html(v)


class ListNameSchema(BaseModel, SafeStringMixin):
    """Validated custom list name (future feature)"""
    name: str = Field(..., min_length=1, max_length=100)
    
    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return cls.validate_no_script(v)


# Utility validation functions
def validate_pagination(page: int, limit: int) -> tuple[int, int]:
    """Validate pagination parameters"""
    page = max(1, min(page, 10000))
    limit = max(1, min(limit, 100))
    return page, limit


def validate_sort_field(field: str, allowed_fields: list[str]) -> str:
    """Validate sort field against whitelist"""
    if field not in allowed_fields:
        raise ValueError(f"Invalid sort field. Allowed: {', '.join(allowed_fields)}")
    return field


def validate_filter_value(value: str, pattern: str) -> str:
    """Validate filter value against regex pattern"""
    if not re.match(pattern, value):
        raise ValueError("Invalid filter value format")
    return value
