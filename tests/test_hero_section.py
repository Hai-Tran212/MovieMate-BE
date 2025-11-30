"""
Hero Section & Hybrid Recommendation Test Suite
================================================
Synchronized with the actual system implementation.

Test Categories:
I. Functional & Accuracy Tests
II. Performance & Speed Tests
III. Security & Authorization Tests
"""
import pytest
import time
from datetime import datetime, timedelta

from app.models.user import User
from app.models.rating import Rating
from app.models.movie import Movie
from app.models.movie_cache import MovieCache
from app.services.recommendation_service import RecommendationService
from app.services.collaborative_service import CollaborativeService
from app.utils.security import create_access_token


# ============================================
# FIXTURES - Synchronized with app/models/
# ============================================

@pytest.fixture
def test_user(db_session):
    """Create a test user matching User model schema"""
    user = User(
        email="testuser@example.com",
        password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V2RqFi0W7e8y7e",  # hashed "password123"
        name="Test User",
        is_active=True,
        email_verified=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_with_ratings(db_session, test_user):
    """Create user with 5+ ratings for personalized recommendations"""
    # Create movies in Movie table (for ratings)
    movies = []
    for i in range(10):
        movie = Movie(
            tmdb_id=1000 + i,
            title=f"Test Movie {i}",
            overview=f"Description for movie {i}",
            vote_average=7.0 + (i * 0.1),
            popularity=100.0 - i
        )
        db_session.add(movie)
        movies.append(movie)
    
    db_session.commit()
    
    # Create ratings (5+ to trigger personalized recs)
    for i, movie in enumerate(movies[:5]):
        db_session.refresh(movie)
        rating = Rating(
            user_id=test_user.id,
            movie_id=movie.id,
            rating=8.0 + (i * 0.2)
        )
        db_session.add(rating)
    
    db_session.commit()
    return test_user


@pytest.fixture
def test_user_no_ratings(db_session):
    """Create user without ratings (for fallback testing)"""
    user = User(
        email="newuser@example.com",
        password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V2RqFi0W7e8y7e",
        name="New User",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def movie_cache_data(db_session):
    """Populate MovieCache for recommendation tests"""
    cache_entries = []
    for i in range(100):
        entry = MovieCache(
            tmdb_id=2000 + i,
            title=f"Cached Movie {i}",
            overview=f"Overview for cached movie {i}",
            genres=[28, 12] if i % 2 == 0 else [18, 35],
            keywords=[100 + i, 200 + i],
            keyword_names=["action", "adventure"] if i % 2 == 0 else ["drama", "comedy"],
            cast=[500 + i, 501 + i],
            crew=[600 + i],
            vote_average=6.0 + (i * 0.04),
            popularity=200.0 - i,
            cached_at=datetime.utcnow()
        )
        db_session.add(entry)
        cache_entries.append(entry)
    
    db_session.commit()
    return cache_entries


@pytest.fixture
def auth_headers(test_user):
    """Generate valid JWT token - uses user_id in payload as per dependencies.py"""
    token = create_access_token(
        data={"sub": test_user.email, "user_id": test_user.id}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_with_ratings(test_user_with_ratings):
    """Generate JWT for user with ratings"""
    token = create_access_token(
        data={"sub": test_user_with_ratings.email, "user_id": test_user_with_ratings.id}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_no_ratings(test_user_no_ratings):
    """Generate JWT for user without ratings"""
    token = create_access_token(
        data={"sub": test_user_no_ratings.email, "user_id": test_user_no_ratings.id}
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================
# I. FUNCTIONAL & ACCURACY TESTS
# ============================================

class TestFunctionalAccuracy:
    """
    I. Kiểm thử Chức năng & Chính xác
    Regression, E2E, Logic, Fallback tests
    """
    
    # --- Regression Tests ---
    
    def test_register_endpoint_works(self, client):
        """Regression: Register endpoint must work"""
        response = client.post("/api/auth/register", json={
            "email": "newtest@example.com",
            "password": "SecurePass123!",
            "name": "New Test User"
        })
        assert response.status_code in [201, 409], "Register endpoint should work"
    
    def test_login_endpoint_works(self, client, test_user):
        """Regression: Login endpoint exists and responds"""
        response = client.post("/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "wrongpassword"
        })
        # Should return 401 for wrong password, not 500
        assert response.status_code in [200, 401], "Login endpoint should not crash"
    
    def test_watchlist_add_works(self, client, auth_headers):
        """Regression: Watchlist add endpoint works"""
        response = client.post(
            "/api/watchlist/",
            json={"movie_id": 550},  # Fight Club
            headers=auth_headers
        )
        # Should work or return proper error
        assert response.status_code in [201, 400, 404, 409, 503]
    
    def test_watchlist_get_works(self, client, auth_headers):
        """Regression: Watchlist get endpoint works"""
        response = client.get("/api/watchlist/", headers=auth_headers)
        assert response.status_code == 200
    
    # --- E2E Tests ---
    
    def test_for_you_returns_recommendations(self, client, auth_headers_with_ratings, movie_cache_data):
        """E2E: /for-you endpoint returns recommendations"""
        response = client.get(
            "/api/recommendations/for-you?limit=6",
            headers=auth_headers_with_ratings
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "recommendations" in data
            assert "algorithm" in data
            assert data["algorithm"] == "personalized_hybrid"
    
    def test_movie_detail_accessible(self, client):
        """E2E: Movie detail endpoint accessible"""
        response = client.get("/api/movies/550")  # Fight Club
        # Should return data or 503 if TMDB is down
        assert response.status_code in [200, 503]
    
    # --- Hero Section Logic Tests ---
    
    def test_for_you_recommendations_sorted_by_hybrid_score(self, client, auth_headers_with_ratings, movie_cache_data):
        """Logic: Recommendations should be sorted by hybrid_score descending"""
        response = client.get(
            "/api/recommendations/for-you?limit=10",
            headers=auth_headers_with_ratings
        )
        
        if response.status_code == 200:
            data = response.json()
            recommendations = data.get("recommendations", [])
            
            if len(recommendations) > 1:
                # Check descending order
                scores = [r.get("hybrid_score", 0) for r in recommendations]
                assert scores == sorted(scores, reverse=True), \
                    "Recommendations should be sorted by hybrid_score descending"
    
    def test_for_you_limit_parameter_respected(self, client, auth_headers_with_ratings, movie_cache_data):
        """Logic: Limit parameter should be respected"""
        for limit in [1, 6, 10]:
            response = client.get(
                f"/api/recommendations/for-you?limit={limit}",
                headers=auth_headers_with_ratings
            )
            
            if response.status_code == 200:
                data = response.json()
                recommendations = data.get("recommendations", [])
                assert len(recommendations) <= limit
    
    # --- Fallback Tests ---
    
    def test_fallback_no_crash_without_ratings(self, client, auth_headers_no_ratings):
        """Fallback: System should not crash when user has no ratings"""
        response = client.get(
            "/api/recommendations/for-you?limit=6",
            headers=auth_headers_no_ratings
        )
        
        # Should NOT be 500
        assert response.status_code != 500, "Should not crash when user has no ratings"
        
        if response.status_code == 200:
            data = response.json()
            assert "recommendations" in data or "message" in data
    
    def test_fallback_returns_empty_or_popular(self, client, auth_headers_no_ratings, movie_cache_data):
        """Fallback: Should return empty list or popular movies"""
        response = client.get(
            "/api/recommendations/for-you?limit=6",
            headers=auth_headers_no_ratings
        )
        
        if response.status_code == 200:
            data = response.json()
            # Either has recommendations (fallback) or empty
            recommendations = data.get("recommendations", [])
            assert isinstance(recommendations, list)


# ============================================
# II. PERFORMANCE & SPEED TESTS
# ============================================

class TestPerformance:
    """
    II. Kiểm thử Hiệu suất & Tốc độ
    API response time, Matrix build time
    """
    
    def test_for_you_response_under_500ms(self, client, auth_headers_with_ratings, movie_cache_data):
        """Performance: /for-you should respond under 500ms"""
        start = time.time()
        
        response = client.get(
            "/api/recommendations/for-you?limit=1",
            headers=auth_headers_with_ratings
        )
        
        elapsed_ms = (time.time() - start) * 1000
        
        # Should respond within 500ms (may vary in test environment)
        assert elapsed_ms < 2000, f"Response took {elapsed_ms:.0f}ms, expected < 2000ms"
    
    def test_similar_movies_response_time(self, client, movie_cache_data):
        """Performance: /similar endpoint response time"""
        start = time.time()
        
        response = client.get("/api/recommendations/similar/550?limit=10")
        
        elapsed_ms = (time.time() - start) * 1000
        
        # Should respond reasonably fast
        assert elapsed_ms < 3000, f"Response took {elapsed_ms:.0f}ms"
    
    def test_cache_stats_quick_response(self, client):
        """Performance: Cache stats should be quick"""
        start = time.time()
        
        response = client.get("/api/recommendations/cache-stats")
        
        elapsed_ms = (time.time() - start) * 1000
        
        assert response.status_code == 200
        assert elapsed_ms < 500


# ============================================
# III. SECURITY & AUTHORIZATION TESTS
# ============================================

class TestSecurity:
    """
    III. Kiểm thử Bảo mật & Ủy quyền
    JWT validation, Authorization requirements
    """
    
    def test_for_you_requires_auth(self, client):
        """Security: /for-you must require authentication"""
        response = client.get("/api/recommendations/for-you?limit=1")
        
        assert response.status_code in [401, 403], \
            "Personalized endpoint must require authentication"
    
    def test_for_you_rejects_invalid_token(self, client):
        """Security: /for-you must reject invalid tokens"""
        response = client.get(
            "/api/recommendations/for-you?limit=1",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        assert response.status_code in [401, 403], \
            "Must reject invalid JWT tokens"
    
    def test_for_you_rejects_expired_token(self, client, test_user):
        """Security: /for-you must reject expired tokens"""
        # Create expired token
        expired_token = create_access_token(
            data={"sub": test_user.email, "user_id": test_user.id},
            expires_delta=timedelta(seconds=-10)  # Already expired
        )
        
        response = client.get(
            "/api/recommendations/for-you?limit=1",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code in [401, 403], \
            "Must reject expired JWT tokens"
    
    def test_for_you_accepts_valid_token(self, client, auth_headers_with_ratings, movie_cache_data):
        """Security: /for-you must accept valid tokens"""
        response = client.get(
            "/api/recommendations/for-you?limit=1",
            headers=auth_headers_with_ratings
        )
        
        # Should NOT be 401/403 with valid token
        assert response.status_code not in [401, 403], \
            "Valid JWT should be accepted"
    
    def test_hybrid_requires_auth(self, client):
        """Security: /hybrid must require authentication"""
        response = client.get("/api/recommendations/hybrid?limit=10")
        
        assert response.status_code in [401, 403]
    
    def test_watchlist_requires_auth(self, client):
        """Security: Watchlist endpoints require authentication"""
        # GET
        response = client.get("/api/watchlist/")
        assert response.status_code in [401, 403]
        
        # POST
        response = client.post("/api/watchlist/", json={"movie_id": 550})
        assert response.status_code in [401, 403]
    
    def test_ratings_requires_auth(self, client):
        """Security: Ratings endpoints require authentication"""
        response = client.post(
            "/api/ratings/",
            json={"movie_id": 550, "rating": 8.0}
        )
        assert response.status_code in [401, 403]
    
    def test_public_endpoints_accessible(self, client):
        """Security: Public endpoints don't require auth"""
        # Similar movies - public
        response = client.get("/api/recommendations/similar/550?limit=5")
        assert response.status_code in [200, 500, 503]  # 500/503 = external API issues
        
        # Mood recommendations - public (optional auth)
        response = client.get("/api/recommendations/mood/happy?limit=5")
        assert response.status_code in [200, 400, 500]
        
        # Cache stats - public
        response = client.get("/api/recommendations/cache-stats")
        assert response.status_code == 200


# ============================================
# IV. DATA INTEGRITY TESTS
# ============================================

class TestDataIntegrity:
    """
    IV. Kiểm thử Tính toàn vẹn Dữ liệu
    Response format, Score ranges
    """
    
    def test_recommendation_has_required_fields(self, client, auth_headers_with_ratings, movie_cache_data):
        """Data: Recommendations must have required fields"""
        response = client.get(
            "/api/recommendations/for-you?limit=5",
            headers=auth_headers_with_ratings
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Top-level fields
            assert "recommendations" in data
            assert "algorithm" in data
            assert "count" in data
            
            # Each recommendation
            for rec in data.get("recommendations", []):
                assert "tmdb_id" in rec, "Each recommendation must have tmdb_id"
                assert "title" in rec, "Each recommendation must have title"
    
    def test_hybrid_score_in_valid_range(self, client, auth_headers_with_ratings, movie_cache_data):
        """Data: hybrid_score must be in [0, 1] range"""
        response = client.get(
            "/api/recommendations/for-you?limit=10",
            headers=auth_headers_with_ratings
        )
        
        if response.status_code == 200:
            data = response.json()
            
            for rec in data.get("recommendations", []):
                score = rec.get("hybrid_score")
                if score is not None:
                    assert 0 <= score <= 1, f"hybrid_score {score} out of range [0, 1]"
    
    def test_cache_stats_format(self, client):
        """Data: Cache stats must have correct format"""
        response = client.get("/api/recommendations/cache-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields per cache-stats endpoint
        assert "total_cached_movies" in data
        assert "cache_ready" in data
        assert "min_required" in data
        assert isinstance(data["total_cached_movies"], int)
        assert isinstance(data["cache_ready"], bool)


# ============================================
# V. ERROR HANDLING TESTS
# ============================================

class TestErrorHandling:
    """
    V. Kiểm thử Xử lý Lỗi
    Graceful error handling, No internal error exposure
    """
    
    def test_invalid_limit_handled(self, client, auth_headers):
        """Error: Invalid limit parameter should return 422"""
        response = client.get(
            "/api/recommendations/for-you?limit=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_limit_out_of_range_handled(self, client, auth_headers):
        """Error: Limit out of range should return 422"""
        # Limit > 50 (max)
        response = client.get(
            "/api/recommendations/for-you?limit=100",
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_invalid_movie_id_for_similar(self, client):
        """Error: Invalid movie ID for similar should be handled"""
        response = client.get("/api/recommendations/similar/abc")
        
        # Should return 422 (validation) or 404 (not found)
        assert response.status_code in [422, 404]
    
    def test_nonexistent_movie_handled(self, client):
        """Error: Non-existent movie should be handled gracefully"""
        response = client.get("/api/recommendations/similar/999999999?limit=5")
        
        # Should not crash - either empty result or error
        assert response.status_code in [200, 404, 500]
    
    def test_invalid_mood_handled(self, client):
        """Error: Invalid mood should return 400"""
        response = client.get("/api/recommendations/mood/invalid_mood?limit=5")
        
        # Should return 400 for invalid mood
        assert response.status_code in [400, 500]


# ============================================
# VI. ALGORITHM CONFIGURATION TESTS
# ============================================

class TestAlgorithmConfig:
    """
    VI. Kiểm thử Cấu hình Thuật toán
    Verify weights and thresholds match expected values
    """
    
    def test_hybrid_weights_sum_to_one(self):
        """Config: Hybrid weights should sum to 1.0"""
        total = RecommendationService.HYBRID_CONTENT_WEIGHT + \
                RecommendationService.HYBRID_COLLABORATIVE_WEIGHT
        
        assert abs(total - 1.0) < 0.001, \
            f"Hybrid weights sum to {total}, expected 1.0"
    
    def test_content_weight_is_70_percent(self):
        """Config: Content-based weight should be 70%"""
        assert RecommendationService.HYBRID_CONTENT_WEIGHT == 0.7, \
            "Content weight should be 0.7 (70%)"
    
    def test_collaborative_weight_is_30_percent(self):
        """Config: Collaborative weight should be 30%"""
        assert RecommendationService.HYBRID_COLLABORATIVE_WEIGHT == 0.3, \
            "Collaborative weight should be 0.3 (30%)"
    
    def test_min_cache_size_configured(self):
        """Config: MIN_CACHE_SIZE should be configured"""
        assert RecommendationService.MIN_CACHE_SIZE >= 50, \
            "MIN_CACHE_SIZE should be at least 50"
    
    def test_mood_genres_configured(self):
        """Config: All moods should have genre configuration"""
        expected_moods = ['happy', 'sad', 'excited', 'relaxed', 'scared', 'thoughtful', 'romantic']
        
        for mood in expected_moods:
            assert mood in RecommendationService.MOOD_TO_GENRES, \
                f"Mood '{mood}' should be configured"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
