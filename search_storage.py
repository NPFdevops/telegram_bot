import json
import os
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# File paths for search data
SEARCH_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'data', 'search_history.json')
SEARCH_FILTERS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'search_filters.json')

# Thread locks for file operations
search_history_lock = threading.Lock()
search_filters_lock = threading.Lock()

# In-memory caches
_search_history_cache: Dict[str, List[Dict]] = {}
_search_filters_cache: Dict[str, Dict] = {}

# Popular collections for suggestions
POPULAR_COLLECTIONS = [
    'cryptopunks', 'bored-ape-yacht-club', 'mutant-ape-yacht-club',
    'azuki', 'clone-x-x-takashi-murakami', 'doodles-official',
    'otherdeed-for-otherside', 'moonbirds', 'veefriends',
    'pudgy-penguins', 'cool-cats-nft', 'world-of-women-nft'
]

# Search categories
SEARCH_CATEGORIES = {
    'art': ['art', 'generative', 'pixel', 'abstract'],
    'gaming': ['gaming', 'metaverse', 'play-to-earn', 'virtual'],
    'pfp': ['profile', 'avatar', 'character', 'pfp'],
    'utility': ['utility', 'membership', 'access', 'dao'],
    'collectibles': ['collectible', 'trading', 'card', 'sport']
}

def init_search_storage() -> None:
    """Initialize search storage system."""
    try:
        # Create data directory if it doesn't exist
        data_dir = os.path.dirname(SEARCH_HISTORY_FILE)
        os.makedirs(data_dir, exist_ok=True)
        
        # Load existing data
        _load_search_history()
        _load_search_filters()
        
        logger.info("Search storage initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing search storage: {e}")

def _load_search_history() -> None:
    """Load search history from file."""
    global _search_history_cache
    try:
        with search_history_lock:
            if os.path.exists(SEARCH_HISTORY_FILE):
                with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    _search_history_cache = json.load(f)
            else:
                _search_history_cache = {}
    except Exception as e:
        logger.error(f"Error loading search history: {e}")
        _search_history_cache = {}

def _save_search_history() -> None:
    """Save search history to file."""
    try:
        with search_history_lock:
            with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(_search_history_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving search history: {e}")

def _load_search_filters() -> None:
    """Load search filters from file."""
    global _search_filters_cache
    try:
        with search_filters_lock:
            if os.path.exists(SEARCH_FILTERS_FILE):
                with open(SEARCH_FILTERS_FILE, 'r', encoding='utf-8') as f:
                    _search_filters_cache = json.load(f)
            else:
                _search_filters_cache = {}
    except Exception as e:
        logger.error(f"Error loading search filters: {e}")
        _search_filters_cache = {}

def _save_search_filters() -> None:
    """Save search filters to file."""
    try:
        with search_filters_lock:
            with open(SEARCH_FILTERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(_search_filters_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving search filters: {e}")

def add_search_to_history(user_id: int, query: str, result_count: int = 0) -> None:
    """Add a search query to user's search history."""
    try:
        user_key = str(user_id)
        current_time = datetime.now().isoformat()
        
        search_entry = {
            'query': query.lower().strip(),
            'timestamp': current_time,
            'result_count': result_count
        }
        
        if user_key not in _search_history_cache:
            _search_history_cache[user_key] = []
        
        # Remove duplicate queries (keep most recent)
        _search_history_cache[user_key] = [
            entry for entry in _search_history_cache[user_key] 
            if entry['query'] != search_entry['query']
        ]
        
        # Add new search to beginning
        _search_history_cache[user_key].insert(0, search_entry)
        
        # Keep only last 20 searches
        _search_history_cache[user_key] = _search_history_cache[user_key][:20]
        
        _save_search_history()
        
    except Exception as e:
        logger.error(f"Error adding search to history: {e}")

def get_user_search_history(user_id: int, limit: int = 10) -> List[str]:
    """Get user's recent search queries."""
    try:
        user_key = str(user_id)
        if user_key not in _search_history_cache:
            return []
        
        # Filter out searches older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_searches = []
        
        for entry in _search_history_cache[user_key]:
            try:
                search_date = datetime.fromisoformat(entry['timestamp'])
                if search_date > cutoff_date:
                    recent_searches.append(entry['query'])
            except:
                continue
        
        return recent_searches[:limit]
        
    except Exception as e:
        logger.error(f"Error getting search history: {e}")
        return []

def get_search_suggestions(user_id: int, query: str = "") -> Dict[str, List[str]]:
    """Get search suggestions for user."""
    try:
        suggestions = {
            'popular': POPULAR_COLLECTIONS[:6],
            'recent': get_user_search_history(user_id, 5),
            'similar': []
        }
        
        # If query provided, find similar collections
        if query:
            query_lower = query.lower().strip()
            similar = []
            
            for collection in POPULAR_COLLECTIONS:
                if query_lower in collection or any(word in collection for word in query_lower.split()):
                    similar.append(collection)
            
            suggestions['similar'] = similar[:5]
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        return {'popular': [], 'recent': [], 'similar': []}

def set_user_search_filters(user_id: int, filters: Dict[str, Any]) -> None:
    """Set search filters for user."""
    try:
        user_key = str(user_id)
        _search_filters_cache[user_key] = {
            **filters,
            'updated_at': datetime.now().isoformat()
        }
        _save_search_filters()
        
    except Exception as e:
        logger.error(f"Error setting search filters: {e}")

def get_user_search_filters(user_id: int) -> Dict[str, Any]:
    """Get search filters for user."""
    try:
        user_key = str(user_id)
        return _search_filters_cache.get(user_key, {})
        
    except Exception as e:
        logger.error(f"Error getting search filters: {e}")
        return {}

def clear_user_search_filters(user_id: int) -> None:
    """Clear search filters for user."""
    try:
        user_key = str(user_id)
        if user_key in _search_filters_cache:
            del _search_filters_cache[user_key]
            _save_search_filters()
        
    except Exception as e:
        logger.error(f"Error clearing search filters: {e}")

def get_category_keywords(category: str) -> List[str]:
    """Get keywords for a search category."""
    return SEARCH_CATEGORIES.get(category.lower(), [])

def categorize_collection(collection_name: str, description: str = "") -> List[str]:
    """Categorize a collection based on name and description."""
    try:
        text = f"{collection_name} {description}".lower()
        categories = []
        
        for category, keywords in SEARCH_CATEGORIES.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        
        return categories
        
    except Exception as e:
        logger.error(f"Error categorizing collection: {e}")
        return []

def cleanup_search_storage() -> None:
    """Clean up old search data."""
    try:
        # Clean up search history older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for user_id in list(_search_history_cache.keys()):
            if user_id in _search_history_cache:
                filtered_history = []
                for entry in _search_history_cache[user_id]:
                    try:
                        search_date = datetime.fromisoformat(entry['timestamp'])
                        if search_date > cutoff_date:
                            filtered_history.append(entry)
                    except:
                        continue
                
                if filtered_history:
                    _search_history_cache[user_id] = filtered_history
                else:
                    del _search_history_cache[user_id]
        
        # Clean up search filters older than 90 days
        filter_cutoff = datetime.now() - timedelta(days=90)
        
        for user_id in list(_search_filters_cache.keys()):
            if user_id in _search_filters_cache:
                try:
                    updated_at = _search_filters_cache[user_id].get('updated_at')
                    if updated_at:
                        update_date = datetime.fromisoformat(updated_at)
                        if update_date < filter_cutoff:
                            del _search_filters_cache[user_id]
                except:
                    del _search_filters_cache[user_id]
        
        _save_search_history()
        _save_search_filters()
        
        logger.info("Search storage cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during search storage cleanup: {e}")