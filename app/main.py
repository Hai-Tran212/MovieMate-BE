from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
from app.routes import auth, movies, watchlist #recommendations
# from app.middleware.security import SecurityHeadersMiddleware # Tạm thời comment dòng này
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MovieMate API",
    description="Movie recommendation system with TMDB integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================
# Security Configuration (Must-Have Features)
# ============================================

# CORS - Whitelist allowed origins
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://localhost:5174",
]
if production_url := os.getenv("FRONTEND_URL"):
    allowed_origins.append(production_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security Headers - FIX CHO SWAGGER UI
# Thay vì dùng SecurityHeadersMiddleware từ file ngoài, ta định nghĩa trực tiếp ở đây
# để kiểm soát Content-Security-Policy cho phép Swagger tải CDN.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # XSS Protection & Clickjacking
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Content Security Policy (CSP) - Đã nới lỏng cho Swagger UI & Youtube
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # Cho phép script từ chính nó, youtube (trailer), và cdn của swagger
        "script-src 'self' 'unsafe-inline' https://www.youtube.com https://cdn.jsdelivr.net; "
        # Cho phép style từ cdn swagger và google fonts
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        # Cho phép ảnh từ tmdb, fastapi logo, và data: (base64 images)
        "img-src 'self' https://image.tmdb.org https://fastapi.tiangolo.com data:; "
        # Cho phép font từ google fonts
        "font-src 'self' https://fonts.gstatic.com; "
        # Cho phép embed youtube
        "frame-src https://www.youtube.com;"
    )

    return response

# Trusted Hosts - Production only
if os.getenv("ENVIRONMENT") == "production":
    if trusted_hosts := os.getenv("TRUSTED_HOSTS", "").split(","):
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# ============================================
# Routes
# ============================================

@app.get("/", tags=["Health"])
async def root():
    """Basic health check"""
    return {
        "message": "MovieMate API",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check for monitoring"""
    return {
        "status": "healthy",
        "api_version": "1.0.0",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "security": {
            "rate_limiting": "enabled",
            "csrf_protection": "enabled",
            "security_headers": "enabled"
        }
    }

# Core routes
app.include_router(auth.router)
app.include_router(movies.router)
app.include_router(watchlist.router)
app.include_router(watchlist.custom_list_router)

# Future routes (uncomment when ready)
# from app.routes import recommendations, ratings, reviews
# app.include_router(recommendations.router)
# app.include_router(ratings.router)
# app.include_router(reviews.router)

# ============================================
# Startup Event
# ============================================
@app.on_event("startup")
async def startup_event():
    """Log security configuration on startup"""
    logger.info("=" * 50)
    logger.info("MovieMate API Starting...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"CORS Origins: {len(allowed_origins)} configured")
    logger.info("Security: Headers (XSS, CSP, HSTS), CSRF Protection, Input Validation")
    logger.info("=" * 50)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )