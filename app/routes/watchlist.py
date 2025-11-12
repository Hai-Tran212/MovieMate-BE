from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, cast

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.schemas.watchlist import (
    WatchlistAdd,
    WatchlistUpdate,
    WatchlistResponse,
    WatchlistStats,
    CustomListCreate,
    CustomListUpdate,
    CustomListResponse,
    CustomListDetailResponse,
    CustomListItemAdd,
    CustomListItemResponse
)
from app.services.watchlist_service import WatchlistService, CustomListService

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])
custom_list_router = APIRouter(prefix="/api/lists", tags=["Custom Lists"])


def get_user_id(user: User) -> int:
    """Helper to extract user_id as int for type safety"""
    return int(user.id)  # type: ignore


# ==================== WATCHLIST ENDPOINTS ====================

@router.post("/", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    watchlist_data: WatchlistAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a movie to user's watchlist
    
    - **movie_id**: TMDB movie ID (required)
    - **notes**: Personal notes about the movie (optional)
    """
    return WatchlistService.add_to_watchlist(db, get_user_id(current_user), watchlist_data)


@router.get("/", response_model=List[WatchlistResponse])
def get_watchlist(
    watched: Optional[bool] = Query(None, description="Filter by watched status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's watchlist
    
    - **watched**: Filter by watched status (true/false/null for all)
    - **skip**: Number of items to skip (pagination)
    - **limit**: Max number of items to return
    """
    return WatchlistService.get_watchlist(db, get_user_id(current_user), watched, skip, limit)


@router.get("/stats", response_model=WatchlistStats)
def get_watchlist_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get watchlist statistics
    
    Returns:
    - Total items in watchlist
    - Watched vs unwatched count
    - Average rating
    """
    return WatchlistService.get_watchlist_stats(db, get_user_id(current_user))


@router.get("/check/{movie_id}", response_model=dict)
def check_in_watchlist(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if a movie is in user's watchlist
    
    Returns:
    - in_watchlist: boolean
    - item_id: watchlist item ID if exists, null otherwise
    - movie_id: TMDB movie ID
    """
    result = WatchlistService.check_in_watchlist(db, get_user_id(current_user), movie_id)
    return {
        "movie_id": movie_id, 
        "in_watchlist": result["in_watchlist"],
        "item_id": result["item_id"]
    }


@router.get("/{item_id}", response_model=WatchlistResponse)
def get_watchlist_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific watchlist item"""
    return WatchlistService.get_watchlist_item(db, get_user_id(current_user), item_id)


@router.patch("/{item_id}", response_model=WatchlistResponse)
def update_watchlist_item(
    item_id: int,
    update_data: WatchlistUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a watchlist item
    
    - **watched**: Mark as watched/unwatched
    - **rating**: Rate the movie (1-10)
    - **notes**: Update personal notes
    """
    return WatchlistService.update_watchlist_item(db, get_user_id(current_user), item_id, update_data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a movie from watchlist"""
    WatchlistService.remove_from_watchlist(db, get_user_id(current_user), item_id)
    return None


# ==================== CUSTOM LISTS ENDPOINTS ====================

@custom_list_router.post("/", response_model=CustomListResponse, status_code=status.HTTP_201_CREATED)
def create_custom_list(
    list_data: CustomListCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new custom list
    
    - **name**: List name (required)
    - **description**: List description (optional)
    - **is_public**: Make list public (default: false)
    """
    return CustomListService.create_list(db, get_user_id(current_user), list_data)


@custom_list_router.get("/", response_model=List[CustomListResponse])
def get_user_lists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all custom lists created by user"""
    lists = CustomListService.get_user_lists(db, get_user_id(current_user))
    
    # Add items count to each list
    for custom_list in lists:
        custom_list.items_count = len(custom_list.list_items)
    
    return lists


@custom_list_router.get("/{list_id}", response_model=CustomListDetailResponse)
def get_custom_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific custom list with all items"""
    return CustomListService.get_list(db, get_user_id(current_user), list_id)


@custom_list_router.patch("/{list_id}", response_model=CustomListResponse)
def update_custom_list(
    list_id: int,
    update_data: CustomListUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a custom list
    
    - **name**: Update list name
    - **description**: Update description
    - **is_public**: Change public/private status
    """
    return CustomListService.update_list(db, get_user_id(current_user), list_id, update_data)


@custom_list_router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a custom list"""
    CustomListService.delete_list(db, get_user_id(current_user), list_id)
    return None


@custom_list_router.post("/{list_id}/items", response_model=CustomListItemResponse, status_code=status.HTTP_201_CREATED)
def add_item_to_list(
    list_id: int,
    item_data: CustomListItemAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a movie to custom list
    
    - **movie_id**: TMDB movie ID (required)
    - **notes**: Personal notes (optional)
    """
    return CustomListService.add_item_to_list(db, get_user_id(current_user), list_id, item_data)


@custom_list_router.get("/{list_id}/items", response_model=List[CustomListItemResponse])
def get_list_items(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all items in a custom list"""
    return CustomListService.get_list_items(db, get_user_id(current_user), list_id)


@custom_list_router.delete("/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item_from_list(
    list_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a movie from custom list"""
    CustomListService.remove_item_from_list(db, get_user_id(current_user), list_id, item_id)
    return None
