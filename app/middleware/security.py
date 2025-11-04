"""
Security middleware for MovieMate API
Implements security headers and CSRF protection (Must-Have features only)
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import secrets
import time
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers (XSS, CSP, HSTS, etc.)"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # XSS Protection
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # HSTS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://www.youtube.com",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' https://image.tmdb.org data:",
            "frame-src https://www.youtube.com",
            "connect-src 'self' https://api.themoviedb.org"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Additional headers
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class CSRFProtection:
    """CSRF token validation for state-changing operations"""
    
    def __init__(self):
        self.tokens: Dict[str, Tuple[str, float]] = {}  # user_id: (token, expiry)
    
    def generate_token(self, user_id: str) -> str:
        """Generate CSRF token for user (1-hour expiry)"""
        token = secrets.token_urlsafe(32)
        self.tokens[user_id] = (token, time.time() + 3600)
        return token
    
    def validate_token(self, user_id: str, token: str) -> bool:
        """Validate CSRF token"""
        if user_id not in self.tokens:
            return False
        
        stored_token, expiry = self.tokens[user_id]
        
        # Check expiry
        if time.time() > expiry:
            del self.tokens[user_id]
            return False
        
        # Constant-time comparison
        return secrets.compare_digest(stored_token, token)
    
    def cleanup_expired(self):
        """Remove expired tokens (call periodically)"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, (_, expiry) in self.tokens.items()
            if current_time > expiry
        ]
        for user_id in expired_users:
            del self.tokens[user_id]
            logger.debug(f"Cleaned expired CSRF token for user {user_id}")


# Global instance
csrf_protection = CSRFProtection()
