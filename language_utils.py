#!/usr/bin/env python3
"""
Language Utilities Module

Handles multi-language support for the Telegram bot including:
- Loading translation files
- User language preferences storage
- Translation helper functions
"""

import json
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Español', 
    'zh': '中文'
}

DEFAULT_LANGUAGE = 'en'

# Global storage for translations and user preferences
translations: Dict[str, Dict[str, Any]] = {}
user_languages: Dict[int, str] = {}  # user_id -> language_code

def load_translations() -> None:
    """
    Load all translation files from the translations directory.
    """
    global translations
    
    translations_dir = os.path.join(os.path.dirname(__file__), 'translations')
    
    for lang_code in SUPPORTED_LANGUAGES.keys():
        translation_file = os.path.join(translations_dir, f'{lang_code}.json')
        
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                translations[lang_code] = json.load(f)
            logger.info(f"Loaded translations for language: {lang_code}")
        except FileNotFoundError:
            logger.error(f"Translation file not found: {translation_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing translation file {translation_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading translation file {translation_file}: {e}")

def get_user_language(user_id: int) -> str:
    """
    Get the preferred language for a user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Language code (defaults to 'en' if not set)
    """
    return user_languages.get(user_id, DEFAULT_LANGUAGE)

def set_user_language(user_id: int, language_code: str) -> bool:
    """
    Set the preferred language for a user.
    
    Args:
        user_id: Telegram user ID
        language_code: Language code to set
        
    Returns:
        True if successful, False if language not supported
    """
    if language_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language code: {language_code}")
        return False
        
    user_languages[user_id] = language_code
    logger.info(f"Set language for user {user_id} to {language_code}")
    return True

def get_text(user_id: int, key_path: str, **kwargs) -> str:
    """
    Get translated text for a user.
    
    Args:
        user_id: Telegram user ID
        key_path: Dot-separated path to the translation key (e.g., 'welcome.greeting')
        **kwargs: Variables to format into the text
        
    Returns:
        Translated and formatted text
    """
    language_code = get_user_language(user_id)
    
    # Get the translation dictionary for the user's language
    lang_dict = translations.get(language_code, translations.get(DEFAULT_LANGUAGE, {}))
    
    # Navigate through the nested dictionary using the key path
    keys = key_path.split('.')
    text = lang_dict
    
    try:
        for key in keys:
            text = text[key]
    except (KeyError, TypeError):
        # Fallback to English if key not found
        logger.warning(f"Translation key '{key_path}' not found for language '{language_code}', falling back to English")
        
        text = translations.get(DEFAULT_LANGUAGE, {})
        try:
            for key in keys:
                text = text[key]
        except (KeyError, TypeError):
            logger.error(f"Translation key '{key_path}' not found in any language")
            return f"[Missing translation: {key_path}]"
    
    # Format the text with provided variables
    if isinstance(text, str) and kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format variable {e} for key '{key_path}'")
        except Exception as e:
            logger.error(f"Error formatting text for key '{key_path}': {e}")
    
    return str(text)

def get_language_options_keyboard() -> list:
    """
    Get inline keyboard options for language selection.
    
    Returns:
        List of inline keyboard button data
    """
    keyboard = []
    
    for lang_code, lang_name in SUPPORTED_LANGUAGES.items():
        # Get the flag and name from translations
        flag_and_name = translations.get('en', {}).get('language', {}).get('options', {}).get(lang_code, f"{lang_code.upper()}")
        keyboard.append({
            'text': flag_and_name,
            'callback_data': f'lang_{lang_code}'
        })
    
    return keyboard

def detect_user_language_from_telegram(telegram_user) -> str:
    """
    Detect user's preferred language from Telegram user object.
    
    Args:
        telegram_user: Telegram User object
        
    Returns:
        Detected language code or default language
    """
    if hasattr(telegram_user, 'language_code') and telegram_user.language_code:
        # Extract the primary language code (e.g., 'en' from 'en-US')
        detected_lang = telegram_user.language_code.split('-')[0].lower()
        
        if detected_lang in SUPPORTED_LANGUAGES:
            return detected_lang
    
    return DEFAULT_LANGUAGE

def initialize_language_system() -> None:
    """
    Initialize the language system by loading all translations.
    """
    logger.info("Initializing language system...")
    load_translations()
    
    if not translations:
        logger.error("No translations loaded! Language system may not work properly.")
    else:
        logger.info(f"Language system initialized with {len(translations)} languages: {list(translations.keys())}")

# Initialize the language system when the module is imported
initialize_language_system()