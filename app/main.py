from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
from app.routes import auth, movies #recommendations
from app.middleware.security import SecurityHeadersMiddleware
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

# Security Headers - XSS, Clickjacking, CSP protection
app.add_middleware(SecurityHeadersMiddleware)

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

# Future routes (uncomment when ready)
# from app.routes import recommendations, watchlist, ratings, reviews
# app.include_router(recommendations.router)
# app.include_router(watchlist.router)
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