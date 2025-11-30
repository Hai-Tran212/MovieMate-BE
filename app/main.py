from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from app.routes import auth, movies, watchlist, recommendations, similar_movies, admin
from app.middleware.security import SecurityHeadersMiddleware
from app.services.background_jobs import background_jobs
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================
# Application Lifespan Management
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events
    
    Startup:
    - Start background jobs (trending/popular updates, cache cleanup)
    - Log security configuration
    
    Shutdown:
    - Stop background jobs gracefully
    """
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 MovieMate API Starting...")
    logger.info(f"   Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"   CORS Origins: {len([os.getenv('FRONTEND_URL')] + ['http://localhost:5173'])} configured")
    logger.info("=" * 60)
    
    # Start background jobs
    try:
        background_jobs.start()
    except Exception as e:
        logger.error(f"Failed to start background jobs: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("🛑 MovieMate API Shutting Down...")
    try:
        background_jobs.shutdown()
        logger.info("   Background jobs stopped")
    except Exception as e:
        logger.error(f"Error stopping background jobs: {str(e)}")
    logger.info("=" * 60)


# Create FastAPI app with lifespan handler
app = FastAPI(
    title="MovieMate API",
    description="Movie recommendation system with TMDB integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
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
    expose_headers=["*"],  # Thêm để expose tất cả headers
)

# ============================================
# Exception Handlers - Đảm bảo CORS cho mọi response
# ============================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom exception handler đảm bảo CORS headers luôn có
    Đặc biệt quan trọng cho 401 Unauthorized errors
    """
    origin = request.headers.get("origin")
    
    # Tạo response
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    
    # Thêm CORS headers nếu origin hợp lệ
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler để đảm bảo CORS headers cho mọi lỗi
    """
    origin = request.headers.get("origin")
    
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
    
    # Thêm CORS headers nếu origin hợp lệ
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

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
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
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
app.include_router(similar_movies.router)  # Real-time similar movies (no cache)
app.include_router(recommendations.router)  # Personalized recommendations (with cache)
app.include_router(admin.router)  # Background jobs management

# Rating system - Should-Have Feature
from app.routes import ratings
app.include_router(ratings.router)

# Future routes (uncomment when ready)
# from app.routes import reviews
# app.include_router(reviews.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )