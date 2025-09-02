import logging
import aiohttp
import asyncio
from typing import Optional, Tuple
from telegram import Update
from telegram.ext import ContextTypes
from language_utils import get_text

logger = logging.getLogger(__name__)

class ErrorType:
    """Error type constants for better error categorization."""
    NETWORK = "network_error"
    API = "api_error"
    TIMEOUT = "timeout_error"
    RATE_LIMIT = "rate_limit_error"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found_error"
    GENERAL = "error"

def categorize_error(error: Exception) -> str:
    """
    Categorize an exception into a specific error type.
    
    Args:
        error: The exception to categorize
        
    Returns:
        str: Error type key for translation lookup
    """
    if isinstance(error, aiohttp.ClientError):
        if isinstance(error, aiohttp.ClientTimeout):
            return ErrorType.TIMEOUT
        elif isinstance(error, aiohttp.ClientConnectionError):
            return ErrorType.NETWORK
        elif isinstance(error, aiohttp.ClientResponseError):
            if error.status == 429:
                return ErrorType.RATE_LIMIT
            elif error.status == 404:
                return ErrorType.NOT_FOUND
            elif 500 <= error.status < 600:
                return ErrorType.API
            else:
                return ErrorType.API
        else:
            return ErrorType.NETWORK
    elif isinstance(error, asyncio.TimeoutError):
        return ErrorType.TIMEOUT
    elif isinstance(error, ValueError):
        return ErrorType.INVALID_INPUT
    else:
        return ErrorType.GENERAL

def get_error_message(user_id: int, error: Exception) -> str:
    """
    Get a user-friendly error message based on the error type.
    
    Args:
        user_id: User ID for language preference
        error: The exception that occurred
        
    Returns:
        str: Localized error message
    """
    error_type = categorize_error(error)
    return get_text(user_id, f'common.{error_type}')

async def handle_command_error(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    error: Exception,
    command_name: str = "command"
) -> None:
    """
    Handle errors that occur during command execution.
    
    Args:
        update: Telegram update object
        context: Bot context
        error: The exception that occurred
        command_name: Name of the command for logging
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    # Log the error with context
    logger.error(
        f"Error in {command_name} for user {user_id}: {type(error).__name__}: {error}",
        exc_info=True
    )
    
    # Send user-friendly error message
    try:
        error_message = get_error_message(user_id, error)
        if update.message:
            await update.message.reply_text(error_message)
        elif update.callback_query:
            await update.callback_query.answer(error_message, show_alert=True)
    except Exception as send_error:
        logger.error(f"Failed to send error message to user {user_id}: {send_error}")

async def handle_api_error(
    error: Exception,
    operation: str = "API operation"
) -> Tuple[bool, Optional[str]]:
    """
    Handle API-related errors and return success status with error type.
    
    Args:
        error: The exception that occurred
        operation: Description of the operation for logging
        
    Returns:
        Tuple[bool, Optional[str]]: (success, error_type_key)
    """
    error_type = categorize_error(error)
    
    logger.error(
        f"Error in {operation}: {type(error).__name__}: {error}",
        exc_info=True
    )
    
    return False, error_type

def log_user_action(user_id: int, action: str, details: str = "") -> None:
    """
    Log user actions for monitoring and debugging.
    
    Args:
        user_id: User ID
        action: Action performed
        details: Additional details
    """
    logger.info(f"User {user_id} performed action '{action}'{f': {details}' if details else ''}")

def log_api_request(endpoint: str, params: dict = None, status: int = None) -> None:
    """
    Log API requests for monitoring.
    
    Args:
        endpoint: API endpoint
        params: Request parameters
        status: Response status code
    """
    params_str = f" with params {params}" if params else ""
    status_str = f" (status: {status})" if status is not None else ""
    logger.info(f"API request to {endpoint}{params_str}{status_str}")