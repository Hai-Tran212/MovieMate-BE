"""
Quick script to populate movie cache for testing
Fetches popular movies from TMDB and caches them locally
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.database import SessionLocal
from app.services.tmdb_service import TMDBService
from app.models.movie_cache import MovieCache
from datetime import datetime, timezone


def populate_cache(num_movies=100):
    """
    Populate movie cache with popular movies from TMDB
    
    Args:
        num_movies: Number of movies to cache (default: 100)
    """
    print(f"🎬 Populating movie cache with {num_movies} popular movies...")
    
    db = SessionLocal()
    tmdb_service = TMDBService()
    
    try:
        # Fetch popular movies from TMDB
        print("📡 Fetching popular movies from TMDB...")
        
        pages_needed = (num_movies // 20) + 1  # TMDB returns 20 per page
        all_movies = []
        
        for page in range(1, pages_needed + 1):
            response = tmdb_service.get_popular(page=page)
            if response and 'results' in response:
                all_movies.extend(response['results'][:num_movies - len(all_movies)])
                print(f"  ✓ Fetched page {page} ({len(all_movies)}/{num_movies} movies)")
                
                if len(all_movies) >= num_movies:
                    break
        
        print(f"\n✅ Fetched {len(all_movies)} movies from TMDB")
        
        # Cache each movie
        print("\n💾 Caching movies in database...")
        cached_count = 0
        skipped_count = 0
        
        for movie_data in all_movies:
            try:
                tmdb_id = movie_data.get('id')
                
                # Check if already cached
                existing = db.query(MovieCache).filter(
                    MovieCache.tmdb_id == tmdb_id
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Fetch full movie details (includes keywords, cast, crew)
                full_details = tmdb_service.get_movie_details(tmdb_id)
                
                if not full_details:
                    continue
                
                # Extract genre IDs
                genres = [g['id'] for g in full_details.get('genres', [])]
                
                # Extract keyword IDs and names
                keywords_data = full_details.get('keywords', {}).get('keywords', [])
                keyword_ids = [k['id'] for k in keywords_data]
                keyword_names = [k['name'] for k in keywords_data]
                
                # Extract cast IDs (top 10)
                cast_data = full_details.get('credits', {}).get('cast', [])
                cast_ids = [c['id'] for c in cast_data[:10]]
                
                # Extract crew IDs (directors, producers, writers)
                crew_data = full_details.get('credits', {}).get('crew', [])
                important_jobs = ['Director', 'Producer', 'Screenplay', 'Writer']
                crew_ids = [
                    c['id'] for c in crew_data 
                    if c.get('job') in important_jobs
                ]
                
                # Create cache entry
                cache_entry = MovieCache(
                    tmdb_id=tmdb_id,
                    title=full_details.get('title', ''),
                    overview=full_details.get('overview', ''),
                    release_date=full_details.get('release_date', ''),
                    poster_path=full_details.get('poster_path', ''),
                    backdrop_path=full_details.get('backdrop_path', ''),
                    vote_average=full_details.get('vote_average', 0.0),
                    popularity=full_details.get('popularity', 0.0),
                    genres=genres,
                    keywords=keyword_ids,
                    keyword_names=keyword_names,
                    cast=cast_ids,
                    crew=crew_ids,
                    cached_at=datetime.now(timezone.utc)
                )
                
                db.add(cache_entry)
                cached_count += 1
                
                if cached_count % 10 == 0:
                    db.commit()
                    print(f"  ✓ Cached {cached_count} movies...")
                
            except Exception as e:
                print(f"  ✗ Error caching movie {movie_data.get('title', 'Unknown')}: {str(e)}")
                continue
        
        # Final commit
        db.commit()
        
        print(f"\n✨ Cache population complete!")
        print(f"  • Cached: {cached_count} new movies")
        print(f"  • Skipped: {skipped_count} (already cached)")
        print(f"  • Total in cache: {db.query(MovieCache).count()}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate movie cache with TMDB data')
    parser.add_argument(
        '--num-movies',
        type=int,
        default=100,
        help='Number of movies to cache (default: 100)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  MOVIE CACHE POPULATION")
    print("=" * 60)
    print()
    
    populate_cache(args.num_movies)
