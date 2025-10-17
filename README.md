# Movie Recommendation System - Backend

FastAPI-based backend with PostgreSQL and ML recommendations.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
uvicorn app.main:app --reload
```

## API Documentation

After running the server, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
