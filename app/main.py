from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routes import auth  #, movies, recommendations
import os

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Movie Recommendation API",
    description="Backend API for movie recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Vite default port
    os.getenv("FRONTEND_URL", ""), # Production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:57257"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "Movie Recommendation API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Import routes (will add later)
app.include_router(auth.router)

# app.include_router(movies.router)
# app.include_router(recommendations.router)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)