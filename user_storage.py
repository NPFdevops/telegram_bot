#!/usr/bin/env python3
"""
User Storage Module

Handles persistent storage of user preferences including:
- Digest settings (enabled/disabled, delivery time)
- Language preferences
- Alert preferences

Uses JSON file-based storage for simplicity and reliability.
"""

import json
import os
from typing import Dict, Any, Optional
import logging
from threading import Lock

logger = logging.getLogger(__name__)

# File paths for storage
STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'data')
DIGEST_SETTINGS_FILE = os.path.join(STORAGE_DIR, 'digest_settings.json')
USER_LANGUAGES_FILE = os.path.join(STORAGE_DIR, 'user_languages.json')
USER_TUTORIAL_FILE = os.path.join(STORAGE_DIR, 'user_tutorial.json')

# Thread locks for file operations
digest_lock = Lock()
language_lock = Lock()
tutorial_lock = Lock()

# In-memory cache
_digest_cache: Dict[int, Dict[str, Any]] = {}
_language_cache: Dict[int, str] = {}
_tutorial_cache: Dict[int, Dict[str, Any]] = {}
_cache_loaded = False

def ensure_storage_dir():
    """Ensure the storage directory exists."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        logger.info(f"Created storage directory: {STORAGE_DIR}")

def load_digest_settings() -> Dict[int, Dict[str, Any]]:
    """Load digest settings from file."""
    ensure_storage_dir()
    
    if not os.path.exists(DIGEST_SETTINGS_FILE):
        return {}
    
    try:
        with open(DIGEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert string keys back to integers
            return {int(k): v for k, v in data.items()}
    except (json.JSONDecodeError, ValueError, IOError) as e:
        logger.error(f"Error loading digest settings: {e}")
        return {}

def save_digest_settings(settings: Dict[int, Dict[str, Any]]) -> bool:
    """Save digest settings to file."""
    ensure_storage_dir()
    
    try:
        # Convert integer keys to strings for JSON serialization
        data = {str(k): v for k, v in settings.items()}
        
        with open(DIGEST_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (IOError, TypeError) as e:
        logger.error(f"Error saving digest settings: {e}")
        return False

def load_user_languages() -> Dict[int, str]:
    """Load user language preferences from file."""
    ensure_storage_dir()
    
    if not os.path.exists(USER_LANGUAGES_FILE):
        return {}
    
    try:
        with open(USER_LANGUAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert string keys back to integers
            return {int(k): v for k, v in data.items()}
    except (json.JSONDecodeError, ValueError, IOError) as e:
        logger.error(f"Error loading user languages: {e}")
        return {}

def save_user_languages(languages: Dict[int, str]) -> bool:
    """Save user language preferences to file."""
    ensure_storage_dir()
    
    try:
        # Convert integer keys to strings for JSON serialization
        data = {str(k): v for k, v in languages.items()}
        
        with open(USER_LANGUAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (IOError, TypeError) as e:
        logger.error(f"Error saving user languages: {e}")
        return False

def init_storage():
    """Initialize storage by loading data into cache."""
    global _digest_cache, _language_cache, _tutorial_cache, _cache_loaded
    
    if _cache_loaded:
        return
    
    _digest_cache = load_digest_settings()
    _language_cache = load_user_languages()
    _tutorial_cache = load_user_tutorial_data()
    _cache_loaded = True
    
    logger.info(f"Loaded {len(_digest_cache)} digest settings and {len(_language_cache)} language preferences")

# Digest Settings Functions
def get_digest_settings(user_id: int) -> Dict[str, Any]:
    """Get digest settings for a user."""
    init_storage()
    return _digest_cache.get(user_id, {'enabled': False, 'time': '08:00'})

def set_digest_settings(user_id: int, settings: Dict[str, Any]) -> bool:
    """Set digest settings for a user."""
    init_storage()
    
    with digest_lock:
        _digest_cache[user_id] = settings
        return save_digest_settings(_digest_cache)

def toggle_digest_enabled(user_id: int) -> bool:
    """Toggle digest enabled status for a user. Returns new status."""
    settings = get_digest_settings(user_id)
    settings['enabled'] = not settings['enabled']
    set_digest_settings(user_id, settings)
    return settings['enabled']

def set_digest_time(user_id: int, time_str: str) -> bool:
    """Set digest delivery time for a user."""
    settings = get_digest_settings(user_id)
    settings['time'] = time_str
    return set_digest_settings(user_id, settings)

def get_all_digest_users() -> Dict[int, Dict[str, Any]]:
    """Get all users with digest enabled."""
    init_storage()
    return {uid: settings for uid, settings in _digest_cache.items() if settings.get('enabled', False)}

# Language Settings Functions
def get_user_language_storage(user_id: int) -> str:
    """Get language preference for a user."""
    init_storage()
    return _language_cache.get(user_id, 'en')

def set_user_language_storage(user_id: int, language_code: str) -> bool:
    """Set language preference for a user."""
    init_storage()
    
    with language_lock:
        _language_cache[user_id] = language_code
        return save_user_languages(_language_cache)

# Cleanup function
def get_all_digest_users():
    """Get all users who have digest enabled"""
    init_storage()
    enabled_users = []
    for user_id, settings in _digest_cache.items():
        if settings.get('enabled', False):
            enabled_users.append({
                'user_id': int(user_id),
                'time': settings.get('time', '09:00')
            })
    return enabled_users

def load_user_tutorial_data() -> Dict[int, Dict[str, Any]]:
    """Load user tutorial data from file."""
    ensure_storage_dir()
    
    if not os.path.exists(USER_TUTORIAL_FILE):
        return {}
    
    try:
        with open(USER_TUTORIAL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert string keys to int
            return {int(k): v for k, v in data.items()}
    except Exception as e:
        logger.error(f"Error loading tutorial data: {e}")
        return {}

def save_user_tutorial_data(tutorial_data: Dict[int, Dict[str, Any]]) -> bool:
    """Save user tutorial data to file."""
    ensure_storage_dir()
    
    try:
        with open(USER_TUTORIAL_FILE, 'w', encoding='utf-8') as f:
            # Convert int keys to string for JSON
            json_data = {str(k): v for k, v in tutorial_data.items()}
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving tutorial data: {e}")
        return False

def get_user_tutorial_status(user_id: int) -> Dict[str, Any]:
    """Get tutorial status for a user."""
    global _tutorial_cache, _cache_loaded
    
    if not _cache_loaded:
        init_storage()
    
    return _tutorial_cache.get(user_id, {
        'completed': False,
        'current_step': 0,
        'steps_completed': [],
        'started_at': None,
        'completed_at': None
    })

def set_user_tutorial_status(user_id: int, status: Dict[str, Any]) -> bool:
    """Set tutorial status for a user."""
    global _tutorial_cache
    
    try:
        with tutorial_lock:
            _tutorial_cache[user_id] = status
            return save_user_tutorial_data(_tutorial_cache)
    except Exception as e:
        logger.error(f"Error setting tutorial status for user {user_id}: {e}")
        return False

def mark_tutorial_step_completed(user_id: int, step: int) -> bool:
    """Mark a specific tutorial step as completed."""
    status = get_user_tutorial_status(user_id)
    if step not in status['steps_completed']:
        status['steps_completed'].append(step)
        status['current_step'] = max(status['current_step'], step + 1)
    return set_user_tutorial_status(user_id, status)

def mark_tutorial_completed(user_id: int) -> bool:
    """Mark tutorial as completed for a user."""
    import datetime
    status = get_user_tutorial_status(user_id)
    status['completed'] = True
    status['completed_at'] = datetime.datetime.now().isoformat()
    return set_user_tutorial_status(user_id, status)

def is_tutorial_completed(user_id: int) -> bool:
    """Check if user has completed the tutorial."""
    status = get_user_tutorial_status(user_id)
    return status.get('completed', False)

def start_tutorial(user_id: int) -> bool:
    """Start tutorial for a user."""
    import datetime
    status = {
        'completed': False,
        'current_step': 0,
        'steps_completed': [],
        'started_at': datetime.datetime.now().isoformat(),
        'completed_at': None
    }
    return set_user_tutorial_status(user_id, status)

def cleanup_storage():
    """Save all cached data to files."""
    if _cache_loaded:
        save_digest_settings(_digest_cache)
        save_user_languages(_language_cache)
        save_user_tutorial_data(_tutorial_cache)
        logger.info("Storage cleanup completed")