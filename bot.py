#!/usr/bin/env python3
"""
Telegram Bot Implementation

A simple Telegram bot created using python-telegram-bot library.
This bot includes basic commands and proper error handling.
"""

import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any
import ssl
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Import language utilities
from language_utils import (
    get_text, set_user_language, get_user_language, 
    get_language_options_keyboard, detect_user_language_from_telegram,
    SUPPORTED_LANGUAGES
)
from error_handler import handle_command_error, log_user_action
from cached_api import (
    fetch_nftpf_projects_cached, fetch_nftpf_project_by_slug_cached,
    search_nftpf_collection_cached, fetch_top_sales_cached,
    fetch_rankings_cached, warm_cache, get_cache_stats, clear_cache
)
from cache_manager import init_cache, cleanup_cache

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - Load from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# NFT API Configuration
NFTPF_API_HOST = os.getenv('NFTPF_API_HOST', 'nftpf-api-v0.p.rapidapi.com')
NFTPF_API_KEY = os.getenv('NFTPF_API_KEY')
if not NFTPF_API_KEY:
    raise ValueError("NFTPF_API_KEY environment variable is required")

OPENSEA_API_URL = os.getenv('OPENSEA_API_URL', 'https://api.opensea.io/api/v1')

# Heroku Configuration
PORT = int(os.getenv('PORT', 8443))
HEROKU_APP_NAME = os.getenv('HEROKU_APP_NAME')
# Use the actual Heroku app URL
WEBHOOK_URL = 'https://nftpf-bot-7d6ac2de74b3.herokuapp.com' if HEROKU_APP_NAME else None


# Command Handlers
def get_main_menu_keyboard(user_id: int) -> list:
    """
    Get the standardized main menu keyboard layout matching the specified design.
    """
    return [
        [
            InlineKeyboardButton('🏆 Rankings', callback_data='main_rankings'),
            InlineKeyboardButton('🔍 Search', callback_data='main_search')
        ],
        [
            InlineKeyboardButton('💰 Top Sales', callback_data='main_top_sales'),
            InlineKeyboardButton('🔥 Popular', callback_data='main_popular')
        ],
        [
            InlineKeyboardButton('🚨 Alerts', callback_data='main_alerts'),
            InlineKeyboardButton('📊 Digest', callback_data='main_digest')
        ],
        [
            InlineKeyboardButton('🌐 Language', callback_data='main_language'),
            InlineKeyboardButton('❓ Help', callback_data='main_help')
        ]
    ]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.
    Sends a welcome message with interactive quick actions matching the specified design.
    """
    try:
        user = update.effective_user
        
        # Detect and set user language if not already set
        current_lang = get_user_language(user.id)
        if current_lang == 'en':  # Default language, try to detect
            detected_lang = detect_user_language_from_telegram(user)
            set_user_language(user.id, detected_lang)
        
        # Check if user is new (hasn't completed tutorial)
        is_new_user = not is_tutorial_completed(user.id)
        
        if is_new_user:
            # Start tutorial for new users
            start_tutorial(user.id)
            welcome_message = get_text(user.id, 'tutorial.interactive.welcome')
            
            keyboard = [
                [InlineKeyboardButton(get_text(user.id, 'tutorial.interactive.next_step'), callback_data='tutorial_step_1')],
                [InlineKeyboardButton(get_text(user.id, 'tutorial.interactive.skip_tutorial'), callback_data='tutorial_skip')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
            
            # Log tutorial start
            log_user_action(user.id, 'tutorial_started', {'language': get_user_language(user.id)})
        else:
            # Create the welcome message matching the image design
            user_name = user.first_name or "Dave Joga"
            welcome_message = f"🤖 Hello {user_name}!\n\nWelcome to NFT Market Insights Bot! I'm here to help you track NFT collections, set price alerts, and stay updated with the latest market trends.\n\n✨ **Let's get you started:**\n\n🎯 **Quick Actions:**\n• 💰 Check floor prices\n• 🏆 Browse top collections\n• 🔔 Set price alerts\n• 🌍 Change language\n\nChoose an option below or use /help for all commands!"
            
            # Use the standardized main menu
            keyboard = get_main_menu_keyboard(user.id)
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
        
        logger.info(f"User {user.id} ({user.username}) started the bot - New user: {is_new_user}")
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        error_message = get_text(user.id, 'errors.general') if 'user' in locals() else "Sorry, something went wrong. Please try again later."
        await update.message.reply_text(error_message)


# NFT API Helper Functions
async def fetch_nftpf_project_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific NFT project by slug from NFTPriceFloor API with caching.
    """
    return await fetch_nftpf_project_by_slug_cached(slug)


async def search_nftpf_collection(collection_name: str, user_id: int = None, filters: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Search for a specific NFT collection by name from NFTPriceFloor API with advanced filtering.
    """
    try:
        # Add search to history if user_id provided
        if user_id:
            add_search_to_history(user_id, collection_name)
        
        collection_name_lower = collection_name.lower().strip()
        
        # First try direct slug lookup for common collections
        # Convert collection name to potential slug format
        potential_slug = collection_name_lower.replace(' ', '-').replace('_', '-')
        
        # Try direct slug fetch first
        logger.info(f"Trying direct slug lookup for '{potential_slug}'")
        detailed_data = await fetch_nftpf_project_by_slug_cached(potential_slug)
        if detailed_data:
            logger.info(f"Found collection via direct slug: {potential_slug}")
            return detailed_data
        
        # Also try some common slug variations
        slug_variations = [
            potential_slug,
            collection_name_lower.replace(' ', ''),  # no spaces
            collection_name_lower.replace(' ', '_'),  # underscores
            f"{potential_slug}-nft",  # with -nft suffix
            f"{potential_slug}-official",  # with -official suffix
        ]
        
        for slug_variant in slug_variations:
            if slug_variant != potential_slug:  # Skip the one we already tried
                logger.info(f"Trying slug variation: '{slug_variant}'")
                detailed_data = await fetch_nftpf_project_by_slug_cached(slug_variant)
                if detailed_data:
                    logger.info(f"Found collection via slug variation: {slug_variant}")
                    return detailed_data
        
        # If direct slug lookup fails, try searching through projects list
        logger.info(f"Direct slug lookup failed, searching through projects list")
        collections_data = await fetch_nftpf_projects_cached(offset=0, limit=500)  # Increased limit
        
        if not collections_data:
            logger.warning("No collections data received from API")
            return None
        
        # Extract projects from the response
        projects = collections_data.get('projects', [])
        if not projects:
            projects = collections_data.get('data', [])
        
        logger.info(f"Searching through {len(projects)} projects for '{collection_name}'")
        
        # Apply filters if provided
        if filters:
            projects = _apply_search_filters(projects, filters)
        
        # Try exact match first
        for project in projects:
            project_name = project.get('name', '').lower().strip()
            if project_name == collection_name_lower:
                logger.info(f"Found exact match: {project.get('name')}")
                slug = project.get('slug')
                if slug:
                    detailed_data = await fetch_nftpf_project_by_slug_cached(slug)
                    if detailed_data:
                        return detailed_data
                return project
        
        # Try partial match
        for project in projects:
            project_name = project.get('name', '').lower().strip()
            # Check if search term is in project name or vice versa
            if (collection_name_lower in project_name or 
                project_name in collection_name_lower or
                any(word in project_name for word in collection_name_lower.split()) or
                any(word in collection_name_lower for word in project_name.split())):
                logger.info(f"Found partial match: {project.get('name')}")
                slug = project.get('slug')
                if slug:
                    detailed_data = await fetch_nftpf_project_by_slug_cached(slug)
                    if detailed_data:
                        return detailed_data
                return project
        
        logger.warning(f"No match found for '{collection_name}'")
        return None
                    
    except Exception as e:
        logger.error(f"Error searching NFT collection: {e}")
        return None


def _apply_search_filters(projects: list, filters: Dict[str, Any]) -> list:
    """
    Apply search filters to the list of projects.
    """
    filtered_projects = projects
    
    # Filter by category
    if filters.get('category'):
        category = filters['category'].lower()
        filtered_projects = [p for p in filtered_projects if categorize_collection(p).lower() == category]
    
    # Filter by price range
    if filters.get('min_price') is not None or filters.get('max_price') is not None:
        min_price = filters.get('min_price', 0)
        max_price = filters.get('max_price', float('inf'))
        filtered_projects = [
            p for p in filtered_projects 
            if min_price <= float(p.get('floorPrice', 0)) <= max_price
        ]
    
    # Filter by volume range
    if filters.get('min_volume') is not None or filters.get('max_volume') is not None:
        min_volume = filters.get('min_volume', 0)
        max_volume = filters.get('max_volume', float('inf'))
        filtered_projects = [
            p for p in filtered_projects 
            if min_volume <= float(p.get('volume', 0)) <= max_volume
        ]
    
    # Filter by trending (top 50 by volume)
    if filters.get('trending'):
        filtered_projects = sorted(
            filtered_projects, 
            key=lambda x: float(x.get('volume', 0)), 
            reverse=True
        )[:50]
    
    # Filter by blue chip (established collections with high volume)
    if filters.get('blue_chip'):
        filtered_projects = [
            p for p in filtered_projects 
            if float(p.get('volume', 0)) > 100 and float(p.get('floorPrice', 0)) > 1
        ]
    
    # Filter by new projects (created recently)
    if filters.get('new_projects'):
        # This would need creation date from API, for now filter by lower volume
        filtered_projects = [
            p for p in filtered_projects 
            if float(p.get('volume', 0)) < 50
        ]
    
    return filtered_projects


# Advanced Search Command Handlers
async def advanced_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /search command for advanced search functionality.
    """
    try:
        user = update.effective_user
        
        if not context.args:
            # Show advanced search menu
            await show_advanced_search_menu(update.message, user.id)
            return
        
        # Perform search with query
        query = " ".join(context.args)
        await perform_advanced_search(update.message, user.id, query)
        
    except Exception as e:
        await handle_command_error(update, context, e, "advanced_search")


async def show_advanced_search_menu(message_or_query, user_id: int) -> None:
    """
    Display the advanced search menu with options.
    """
    text = get_text(user_id, 'advanced_search.menu_title')
    
    # Get user's current filters
    current_filters = get_user_search_filters(user_id)
    filter_summary = ""
    
    if current_filters:
        filter_parts = []
        if current_filters.get('category'):
            filter_parts.append(f"📂 {current_filters['category']}")
        if current_filters.get('min_price') or current_filters.get('max_price'):
            min_p = current_filters.get('min_price', 0)
            max_p = current_filters.get('max_price', '∞')
            filter_parts.append(f"💰 {min_p}-{max_p} ETH")
        if current_filters.get('trending'):
            filter_parts.append("🔥 Trending")
        if current_filters.get('blue_chip'):
            filter_parts.append("💎 Blue Chip")
        
        if filter_parts:
            filter_summary = f"\n\n🔍 **{get_text(user_id, 'advanced_search.active_filters')}:**\n" + "\n".join(filter_parts)
    
    text += filter_summary
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, 'advanced_search.quick_search'), callback_data="search_quick"),
            InlineKeyboardButton(get_text(user_id, 'advanced_search.filters'), callback_data="search_filters")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'advanced_search.suggestions'), callback_data="search_suggestions"),
            InlineKeyboardButton(get_text(user_id, 'advanced_search.history'), callback_data="search_history")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="menu_main")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(message_or_query, 'edit_text'):
        await message_or_query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await message_or_query.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def perform_advanced_search(message_or_query, user_id: int, query: str, filters: Dict[str, Any] = None) -> None:
    """
    Perform advanced search with filters and display results.
    """
    try:
        # Get user filters if not provided
        if filters is None:
            filters = get_user_search_filters(user_id)
        
        # Send searching message
        searching_text = f"🔍 {get_text(user_id, 'advanced_search.searching', query=query)}"
        
        if hasattr(message_or_query, 'edit_text'):
            searching_msg = message_or_query
            await searching_msg.edit_text(searching_text, parse_mode='Markdown')
        else:
            searching_msg = await message_or_query.reply_text(searching_text, parse_mode='Markdown')
        
        # Perform search
        collection_data = await search_nftpf_collection(query, user_id, filters)
        
        if not collection_data:
            # Show no results message with suggestions
            await show_search_no_results(searching_msg, user_id, query)
            return
        
        # Show search results
        await show_search_results(searching_msg, user_id, collection_data, query)
        
    except Exception as e:
        logger.error(f"Error in advanced search: {e}")
        error_text = get_text(user_id, 'advanced_search.error')
        if hasattr(message_or_query, 'edit_text'):
            await message_or_query.edit_text(error_text, parse_mode='Markdown')
        else:
            await message_or_query.reply_text(error_text, parse_mode='Markdown')


# NFT Command Handlers
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /price command.
    Get NFT collection floor price and detailed information using the projects/{slug} endpoint.
    """
    try:
        user = update.effective_user
        
        # Check if collection name is provided
        if not context.args:
            usage_message = get_text(user.id, 'price.usage')
            await update.message.reply_text(usage_message, parse_mode='Markdown')
            return
        
        collection_name = " ".join(context.args)
        
        # Send "searching" message with visual indicator
        searching_text = f"🔍 {get_text(user.id, 'price.searching', collection=collection_name)}"
        searching_msg = await update.message.reply_text(searching_text, parse_mode='Markdown')
        
        # First search for collection to get the slug
        collection_data = await search_nftpf_collection(collection_name, user.id)
        
        if not collection_data:
            not_found_text = get_text(user.id, 'price.not_found', collection=collection_name)
            await searching_msg.edit_text(not_found_text, parse_mode='Markdown')
            return
        
        # Get the slug from search results
        slug = collection_data.get('slug') or collection_data.get('details', {}).get('slug')
        if not slug:
            not_found_text = get_text(user.id, 'price.not_found', collection=collection_name)
            await searching_msg.edit_text(not_found_text, parse_mode='Markdown')
            return
        
        # Fetch detailed project data using the projects/{slug} endpoint
        project_data = await fetch_nftpf_project_by_slug_cached(slug)
        
        if not project_data:
            error_text = get_text(user.id, 'price.error')
            await searching_msg.edit_text(error_text, parse_mode='Markdown')
            return
        
        # Extract data from the detailed project response
        stats = project_data.get('stats', {})
        details = project_data.get('details', {})
        
        name = details.get('name', 'Unknown')
        
        # Floor price information from stats
        floor_info = stats.get('floorInfo', {})
        floor_price_eth = floor_info.get('currentFloorNative', 0)
        floor_price_usd = floor_info.get('currentFloorUsd', 0)
        
        # 24h change from floor temporality
        floor_temporality = stats.get('floorTemporalityUsd', {})
        change_24h = floor_temporality.get('diff24h', 0)
        
        # Volume and sales data from sales temporality
        sales_temporality = stats.get('salesTemporalityUsd', {})
        volume_data = sales_temporality.get('volume', {})
        count_data = sales_temporality.get('count', {})
        average_data = sales_temporality.get('average', {})
        
        volume_24h_usd = volume_data.get('val24h', 0)
        sales_24h = count_data.get('val24h', 0)
        avg_sale_price_usd = average_data.get('val24h', 0)
        
        # Convert volume from USD to ETH (approximate)
        volume_24h_eth = volume_24h_usd / floor_price_usd if floor_price_usd > 0 else 0
        avg_sale_price_eth = avg_sale_price_usd / floor_price_usd * floor_price_eth if floor_price_usd > 0 and floor_price_eth > 0 else 0
        
        # Supply information from stats
        total_supply = stats.get('totalSupply', 0)
        listed_count = stats.get('listedCount', 0)
        
        # Official links from social media
        social_media = details.get('socialMedia', [])
        website = ''
        twitter = ''
        discord = ''
        
        for social in social_media:
            if social.get('name') == 'website':
                website = social.get('url', '')
            elif social.get('name') == 'twitter':
                twitter = social.get('url', '')
            elif social.get('name') == 'discord':
                discord = social.get('url', '')
        
        # Create hyperlink for collection name to NFTPriceFloor
        collection_link = f"[{name}](https://nftpricefloor.com/{slug}?utm_source=telegram_bot)"
        
        # Format the response according to user specifications
        response_text = f"📊 **{collection_link}**\n\n"
        
        # Floor price in ETH and USD
        if floor_price_eth > 0:
            response_text += f"💎 **Floor Price:** {floor_price_eth:.3f} ETH (${floor_price_usd:,.0f})\n"
        else:
            response_text += f"💎 **Floor Price:** Not available\n"
        
        # 24h Change in %
        if change_24h != 0:
            sign = "+" if change_24h >= 0 else ""
            emoji = "📈" if change_24h >= 0 else "📉"
            response_text += f"{emoji} **24h Change:** {sign}{change_24h:.1f}%\n"
        else:
            response_text += f"📊 **24h Change:** 0.0%\n"
        
        # Volume in ETH (number of sales)
        if volume_24h_eth > 0:
            if volume_24h_eth >= 1000:
                volume_str = f"{volume_24h_eth/1000:.1f}K ETH"
            else:
                volume_str = f"{volume_24h_eth:.2f} ETH"
            response_text += f"💰 **Volume:** {volume_str} ({sales_24h} sales)\n"
        else:
            response_text += f"💰 **Volume:** 0 ETH (0 sales)\n"
        
        # Listings (total supply)
        if total_supply > 0:
            listings_text = f"{listed_count:,}" if listed_count > 0 else "0"
            response_text += f"📋 **Listings:** {listings_text} ({total_supply:,} total supply)\n"
        
        # Average Sale Price
        if avg_sale_price_eth > 0:
            response_text += f"📊 **Avg Sale:** {avg_sale_price_eth:.3f} ETH\n"
        
        # Official Links
        links = []
        if website:
            links.append(f"[Website]({website})")
        if twitter:
            links.append(f"[Twitter]({twitter})")
        if discord:
            links.append(f"[Discord]({discord})")
        
        if links:
            response_text += f"\n🔗 **Official Links:** {' • '.join(links)}\n"
        
        # Link to the chart (NFTPriceFloor collection page)
        response_text += f"\n📈 [View Chart & Analytics](https://nftpricefloor.com/{slug}?utm_source=telegram_bot)\n"
        
        response_text += "\n🔄 *Data from NFTPriceFloor API*"
        
        await searching_msg.edit_text(response_text, parse_mode='Markdown', disable_web_page_preview=True)
        log_user_action(update.effective_user.id, "price_command", f"collection: {collection_name}")
        
    except Exception as e:
        await handle_command_error(update, context, e, "price_command")


async def format_top_sales_message(data: Dict[str, Any], user_id: int) -> str:
    """
    Format top sales data into a readable message.
    """
    # Handle both array format and object format
    if isinstance(data, list):
        sales = data[:10]  # Show top 10 sales
    elif isinstance(data, dict) and 'sales' in data:
        sales = data['sales'][:10]  # Show top 10 sales
    else:
        return get_text(user_id, 'top_sales.no_data')
    
    if not sales:
        return get_text(user_id, 'top_sales.no_data')
    message_lines = [get_text(user_id, 'top_sales.title')]
    
    for i, sale in enumerate(sales, 1):
        # Extract data from the actual API response structure
        project = sale.get('project', {})
        collection_name = project.get('name', 'Unknown')
        token_id = sale.get('tokenId', '')
        price_eth = sale.get('nativePrice', 0)
        price_usd = sale.get('usdPrice', 0)
        transaction_hash = sale.get('transactionId', '')
        timestamp = sale.get('timestamp', 0)
        
        # Calculate time ago from timestamp (microseconds)
        import datetime
        if timestamp:
            try:
                # Convert microseconds to seconds
                timestamp_seconds = timestamp / 1000000
                sale_time = datetime.datetime.fromtimestamp(timestamp_seconds)
                now = datetime.datetime.now()
                time_diff = now - sale_time
                
                if time_diff.days > 0:
                    time_ago = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    time_ago = f"{hours}h ago"
                elif time_diff.seconds > 60:
                    minutes = time_diff.seconds // 60
                    time_ago = f"{minutes}m ago"
                else:
                    time_ago = "Just now"
            except:
                time_ago = "Unknown time"
        else:
            time_ago = "Unknown time"
        
        # Format prices
        price_eth_str = f"{price_eth:.3f}" if price_eth else "0"
        price_usd_str = f"{price_usd:,.0f}" if price_usd else "0"
        
        # Create Etherscan link if transaction hash is available
        etherscan_link = f"https://etherscan.io/tx/{transaction_hash}" if transaction_hash else ""
        
        # Format the sale item
        sale_text = get_text(user_id, 'top_sales.item').format(
            rank=i,
            collection=collection_name,
            token_id=token_id,
            price=price_eth_str,
            usd=price_usd_str,
            time_ago=time_ago
        )
        
        # Add Etherscan link if available
        if etherscan_link:
            sale_text += f"   🔗 [View Transaction]({etherscan_link})\n"
        
        message_lines.append(sale_text)
    
    message_lines.append("")
    message_lines.append(get_text(user_id, 'top_sales.footer'))
    
    return "\n".join(message_lines)


def get_top_sales_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Create keyboard for top sales command.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                get_text(user_id, 'top_sales.refresh'),
                callback_data='top_sales_refresh'
            )
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, 'top_sales.view_more'),
                url='https://nftpricefloor.com/rankings'
            )
        ],
        [
            InlineKeyboardButton(
                get_text(user_id, 'navigation.back_to_menu'),
                callback_data='main_menu'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def top_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /top_sales command.
    Show top NFT collections by 24h volume.
    """
    try:
        user_id = update.effective_user.id
        
        # Send loading message
        loading_msg = await update.message.reply_text(
            get_text(user_id, 'top_sales.loading')
        )
        
        # Fetch top sales data
        data = await fetch_top_sales_cached()
        
        if data:
            message = await format_top_sales_message(data, user_id)
            keyboard = get_top_sales_keyboard(user_id)
            
            await loading_msg.edit_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            log_user_action(user_id, "top_sales_command", "success")
        else:
            await loading_msg.edit_text(
                get_text(user_id, 'top_sales.error')
            )
            
    except Exception as e:
        await handle_command_error(update, context, e, "top_sales_command")


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /alerts command.
    Manage price alerts for NFT collections.
    """
    try:
        user_id = update.effective_user.id
        log_user_action(user_id, "alerts_command", "initiated")
        
        # Check if user provided arguments
        if not context.args:
            # Show help for alerts command
            help_text = get_text(user_id, 'alerts.help')
            await update.message.reply_text(help_text, parse_mode='Markdown')
            return
        
        command = context.args[0].lower()
        
        if command == "list":
            # For now, show a placeholder message
            response_text = get_text(user_id, 'alerts.list_empty')
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        elif command == "add":
            if len(context.args) < 3:
                usage_text = get_text(user_id, 'alerts.add_usage')
                await update.message.reply_text(usage_text, parse_mode='Markdown')
                return
            
            collection_name = context.args[1]
            try:
                target_price = float(context.args[2])
            except ValueError:
                invalid_price_text = get_text(user_id, 'alerts.invalid_price')
                await update.message.reply_text(invalid_price_text, parse_mode='Markdown')
                return
            
            # For now, show a success message (in a real implementation, this would save to database)
            success_text = get_text(user_id, 'alerts.add_success')
            response_text = success_text.format(collection=collection_name, price=target_price)
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        elif command == "remove":
            if len(context.args) < 2:
                remove_usage_text = get_text(user_id, 'alerts.remove_usage')
                await update.message.reply_text(remove_usage_text, parse_mode='Markdown')
                return
            
            alert_id = context.args[1]
            # For now, show a placeholder message
            remove_success_text = get_text(user_id, 'alerts.remove_success')
            response_text = remove_success_text.format(alert_id=alert_id)
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        else:
            unknown_command_text = get_text(user_id, 'alerts.unknown_command')
            await update.message.reply_text(unknown_command_text, parse_mode='Markdown')
        
        log_user_action(user_id, "alerts_command", "success")
        
    except Exception as e:
        await handle_command_error(update, e, user_id)


async def fetch_nftpf_projects(offset: int = 0, limit: int = 10) -> Optional[Dict[str, Any]]:
    """
    Fetch NFT projects data from NFTPriceFloor API (cached version).
    """
    return await fetch_nftpf_projects_cached(offset=offset, limit=limit)


async def rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /rankings command.
    Show top NFT collections by market cap.
    """
    try:
        user = update.effective_user
        log_user_action(user.id, "rankings_command", "initiated")
        
        # Send "loading" message
        loading_text = get_text(user.id, 'rankings.loading')
        loading_msg = await update.message.reply_text(loading_text)
        
        # Fetch NFT collections data from NFTPriceFloor API
        collections_data = await fetch_rankings_cached(offset=0, limit=10)
        
        if not collections_data:
            error_text = get_text(user.id, 'rankings.error')
            await loading_msg.edit_text(error_text)
            return
        
        # Handle both 'data' and 'projects' keys for API response compatibility
        projects = collections_data.get('data', collections_data.get('projects', []))
        if not projects:
            no_data_text = get_text(user.id, 'rankings.no_data')
            await loading_msg.edit_text(no_data_text)
            return
        
        # Format the rankings response
        response_text = get_text(user.id, 'rankings.title')
        
        for i, project in enumerate(projects[:10], 1):
            name = project.get('name', 'Unknown')
            slug = project.get('slug', '')
            stats = project.get('stats', {})
            floor_info = stats.get('floorInfo', {})
            
            floor_price_eth = floor_info.get('currentFloorNative', 0)
            floor_price_usd = floor_info.get('currentFloorUsd', 0)
            
            # Get 24h price change from floorTemporalityUsd and floorTemporalityNative
            floor_temp_usd = stats.get('floorTemporalityUsd', {})
            floor_temp_native = stats.get('floorTemporalityNative', {})
            price_change_24h = floor_temp_native.get('diff24h', 0)
            price_change_24h_usd = floor_temp_usd.get('diff24h', 0)
            
            # Get 24h volume and sales count
            volume_data = stats.get('volume', {})
            count_data = stats.get('count', {})
            sales_temp_native = stats.get('salesTemporalityNative', {})
            volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
            sales_24h = count_data.get('val24h', 0)
            sales_count_native = sales_temp_native.get('count', {}).get('val24h', 0)
            
            # Format 24h price change
            if price_change_24h:
                sign = "+" if price_change_24h >= 0 else ""
                price_change_native = f"{sign}{price_change_24h:.1f}%"
                price_change_usd = f"({sign}{price_change_24h_usd:.1f}%)"
                price_change_display = f"{price_change_native} {price_change_usd}"
            else:
                price_change_display = "N/A"
            
            # Format floor price in ETH and USD
            floor_eth = f"{floor_price_eth:.1f} ETH" if floor_price_eth else "N/A"
            floor_usd = f"(${floor_price_usd:,.0f})" if floor_price_usd else "(N/A)"
            floor_display = f"{floor_eth} {floor_usd}" if floor_price_eth and floor_price_usd else "N/A"
            
            # Format 24h volume and sales
            vol_24h = f"{volume_24h:.1f} ETH" if volume_24h else "N/A"
            sales_count_display = f"{int(sales_24h)} sales" if sales_24h else "0 sales"
            volume_sales_display = f"{vol_24h} ({sales_count_display})" if volume_24h else "N/A"
            
            # Create hyperlink for collection name
            collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
            
            response_text += (
                f"{i}. {collection_link}\n"
                f"    📈 24h Change: {price_change_display}\n"
                f"    🏠 Floor: {floor_display}\n"
                f"    📊 24h Volume: {volume_sales_display}\n\n"
            )
        
        # Add pagination and back to menu buttons
        next_button_text = get_text(user.id, 'rankings.next_button')
        back_to_menu_text = get_text(user.id, 'common.back')
        keyboard = [
            [InlineKeyboardButton(next_button_text, callback_data="rankings_next_10")],
            [InlineKeyboardButton(back_to_menu_text, callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        footer_text = get_text(user.id, 'rankings.footer')
        response_text += f"\n{footer_text}"
        
        await loading_msg.edit_text(
            response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        log_user_action(user.id, "rankings_command", "success")
        
    except Exception as e:
        await handle_command_error(update, e, user.id)


async def rankings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries for rankings pagination.
    """
    try:
        query = update.callback_query
        user = query.from_user
        await query.answer()
        
        if query.data == "rankings_next_10":
            # Send "loading" message with visual indicator
            loading_text = f"⏳ {get_text(user.id, 'rankings.loading_next')}"
            await query.edit_message_text(loading_text)
            
            # Fetch next 10 collections
            collections_data = await fetch_rankings_cached(offset=10, limit=10)
            
            if not collections_data:
                error_text = get_text(user.id, 'rankings.error')
                await query.edit_message_text(error_text)
                return
            
            # fetch_rankings_cached returns a list directly
            projects = collections_data if isinstance(collections_data, list) else []
            if not projects:
                no_more_text = get_text(user.id, 'rankings.no_more')
                await query.edit_message_text(no_more_text)
                return
            
            # Format the response for next 10
            response_text = get_text(user.id, 'rankings.title_next')
            
            for i, project in enumerate(projects[:10], 11):
                name = project.get('name', 'Unknown')
                slug = project.get('slug', '')
                stats = project.get('stats', {})
                floor_info = stats.get('floorInfo', {})
                
                floor_price_eth = floor_info.get('currentFloorNative', 0)
                floor_price_usd = floor_info.get('currentFloorUsd', 0)
                
                # Get 24h price change from floorTemporalityUsd and floorTemporalityNative
                floor_temp_usd = stats.get('floorTemporalityUsd', {})
                floor_temp_native = stats.get('floorTemporalityNative', {})
                price_change_24h = floor_temp_native.get('diff24h', 0)
                price_change_24h_usd = floor_temp_usd.get('diff24h', 0)
                
                # Get 24h volume and sales count
                volume_data = stats.get('volume', {})
                count_data = stats.get('count', {})
                sales_temp_native = stats.get('salesTemporalityNative', {})
                volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
                sales_24h = count_data.get('val24h', 0)
                sales_count_native = sales_temp_native.get('count', {}).get('val24h', 0)
                
                # Format 24h price change
                if price_change_24h:
                    sign = "+" if price_change_24h >= 0 else ""
                    price_change_native = f"{sign}{price_change_24h:.1f}%"
                    price_change_usd = f"({sign}{price_change_24h_usd:.1f}%)"
                    price_change_display = f"{price_change_native} {price_change_usd}"
                else:
                    price_change_display = "N/A"
                
                # Format floor price in ETH and USD
                floor_eth = f"{floor_price_eth:.1f} ETH" if floor_price_eth else "N/A"
                floor_usd = f"(${floor_price_usd:,.0f})" if floor_price_usd else "(N/A)"
                floor_display = f"{floor_eth} {floor_usd}" if floor_price_eth and floor_price_usd else "N/A"
                
                # Format 24h volume and sales
                vol_24h = f"{volume_24h:.1f} ETH" if volume_24h else "N/A"
                sales_count = f"{int(sales_24h)} sales" if sales_24h else "0 sales"
                volume_sales_display = f"{vol_24h} ({sales_count})" if volume_24h else "N/A"
                
                # Create hyperlink for collection name
                collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
                
                response_text += (
                    f"{i}. {collection_link}\n"
                    f"    📈 24h Change: {price_change_display}\n"
                    f"    🏠 Floor: {floor_display}\n"
                    f"    📊 24h Volume: {volume_sales_display}\n\n"
                )
            
            # Add back and back to menu buttons
            back_button_text = get_text(user.id, 'rankings.back_button')
            back_to_menu_text = get_text(user.id, 'common.back')
            keyboard = [
                [InlineKeyboardButton(back_button_text, callback_data="rankings_back_10")],
                [InlineKeyboardButton(back_to_menu_text, callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            footer_text = get_text(user.id, 'rankings.footer')
            response_text += f"\n{footer_text}"
            
            await query.edit_message_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            log_user_action(user.id, "rankings_next", "success")
            
        elif query.data == "rankings_back_10":
            # Go back to top 10 - use callback-friendly version
            await rankings_command_from_callback(query, user.id)
            log_user_action(user.id, "rankings_back", "success")
            
    except Exception as e:
        # For callback queries, we need to handle errors differently
        from error_handler import get_error_message
        error_message = get_error_message(user.id, e)
        await query.edit_message_text(error_message)
        logger.error(f"Error in rankings_callback for user {user.id}: {type(e).__name__}: {e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command.
    Provides usage instructions and available commands.
    """
    try:
        user = update.effective_user
        
        # Build help text using translations
        help_text = get_text(user.id, 'help.title')
        
        # Add each command
        commands = [
            get_text(user.id, 'help.commands.start'),
            get_text(user.id, 'help.commands.help'),
            get_text(user.id, 'help.commands.price'),
            get_text(user.id, 'help.commands.rankings'),
            get_text(user.id, 'help.commands.alerts'),
            get_text(user.id, 'help.commands.language')
        ]
        
        help_text += '\n'.join(commands)
        help_text += get_text(user.id, 'help.usage')
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        logger.info(f"Help command used by user {user.id}")
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        error_message = get_text(update.effective_user.id, 'errors.general')
        await update.message.reply_text(error_message)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /language command.
    Shows current language and provides options to change it.
    """
    try:
        user = update.effective_user
        
        # Show current language
        current_lang = get_user_language(user.id)
        current_text = get_text(user.id, 'language.current')
        select_text = get_text(user.id, 'language.select')
        
        # Create inline keyboard for language selection
        keyboard_options = get_language_options_keyboard()
        keyboard = []
        
        # Arrange buttons in rows (2 per row)
        for i in range(0, len(keyboard_options), 2):
            row = []
            for j in range(i, min(i + 2, len(keyboard_options))):
                option = keyboard_options[j]
                row.append(InlineKeyboardButton(
                    text=option['text'],
                    callback_data=option['callback_data']
                ))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"{current_text}\n\n{select_text}"
        await update.message.reply_text(message_text, reply_markup=reply_markup)
        
        logger.info(f"Language command used by user {user.id}")
    except Exception as e:
        logger.error(f"Error in language_command: {e}")
        error_message = get_text(update.effective_user.id, 'errors.general')
        await update.message.reply_text(error_message)


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle language selection callbacks.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        callback_data = query.data
        
        if callback_data.startswith('lang_'):
            language_code = callback_data.replace('lang_', '')
            
            if language_code in SUPPORTED_LANGUAGES:
                # Set the new language
                set_user_language(user.id, language_code)
                
                # Show confirmation and redirect back to help menu with updated content
                confirmation_text = get_text(user.id, 'language.changed')
                
                # Create a keyboard to go back to help menu with updated language
                keyboard = [
                    [InlineKeyboardButton(get_text(user.id, 'common.back_to_help'), callback_data='main_help')],
                    [InlineKeyboardButton(get_text(user.id, 'navigation.back'), callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(confirmation_text, reply_markup=reply_markup)
                
                logger.info(f"User {user.id} changed language to {language_code}")
            else:
                error_message = get_text(user.id, 'errors.invalid_command')
                await query.edit_message_text(error_message)
        
    except Exception as e:
        logger.error(f"Error in language_callback: {e}")
        try:
            error_message = get_text(update.effective_user.id, 'errors.general')
            await query.edit_message_text(error_message)
        except:
            pass


# Quick Action Callback Handlers
async def quick_actions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle quick action button callbacks from the welcome message.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        callback_data = query.data
        
        # Handle unified main menu options
        if callback_data == 'main_rankings':
            await rankings_command_from_callback(query, user.id)
        elif callback_data == 'main_search':
            await show_collection_search(query, user.id)
        elif callback_data == 'main_top_sales':
            # Show top sales with back to main menu option
            await show_top_sales_from_callback(query, user.id)
        elif callback_data == 'main_popular':
            await show_popular_collections(query, user.id)
        elif callback_data == 'main_alerts':
            await show_alert_setup(query, user.id)
        elif callback_data == 'main_digest':
            await show_digest_menu(query, user.id)
        elif callback_data == 'main_language':
            await language_command_from_callback(query, user.id)
        elif callback_data == 'main_help':
            await show_help_menu(query, user.id)
        elif callback_data == 'main_tutorial':
            await show_tutorial(query, user.id)
        # Handle legacy quick actions for backward compatibility
        elif callback_data == 'quick_popular':
            await show_popular_collections(query, user.id)
        elif callback_data == 'quick_rankings':
            await rankings_command_from_callback(query, user.id)
        elif callback_data == 'quick_alert':
            await show_alert_setup(query, user.id)
        elif callback_data == 'quick_tutorial':
            await show_tutorial(query, user.id)
        elif callback_data == 'quick_help':
            await show_help_menu(query, user.id)
        elif callback_data == 'more_options':
            await show_tutorial_menu(query, user.id)
        elif callback_data == 'search_collections':
            await show_collection_search(query, user.id)
        elif callback_data == 'quick_access':
            await show_quick_access_collections(query, user.id)
        elif callback_data.startswith('collection_'):
            collection_slug = callback_data.replace('collection_', '')
            await get_collection_price_from_callback(query, user.id, collection_slug)
        elif callback_data.startswith('price_'):
            collection_slug = callback_data.replace('price_', '')
            await get_collection_price_from_callback(query, user.id, collection_slug)
        elif callback_data.startswith('alert_'):
            collection_slug = callback_data.replace('alert_', '')
            await setup_alert_from_callback(query, user.id, collection_slug)
        elif callback_data.startswith('popular_page_'):
            page = int(callback_data.replace('popular_page_', ''))
            await show_popular_collections(query, user.id, page)
        elif callback_data.startswith('collections_page_'):
            page = int(callback_data.replace('collections_page_', ''))
            await show_popular_collections(query, user.id, page)
        elif callback_data == 'back_to_popular':
            await show_popular_collections(query, user.id)
        elif callback_data == 'main_menu':
            await show_main_menu(query, user.id)
        elif callback_data == 'back_to_main':
            # Navigate back to the unified main menu
            await show_main_menu(query, user.id)
        elif callback_data == 'help_price':
            await show_price_help(query, user.id)
        elif callback_data == 'help_rankings':
            await show_rankings_help(query, user.id)
        elif callback_data == 'help_alerts':
            await show_alerts_help(query, user.id)
        elif callback_data == 'alerts_list':
            # Redirect to alerts command functionality
            await show_alert_setup(query, user.id)
        elif callback_data.startswith('menu_'):
            menu_type = callback_data.replace('menu_', '')
            if menu_type == 'market':
                await rankings_command_from_callback(query, user.id)
            elif menu_type == 'collections':
                await show_popular_collections(query, user.id)
            elif menu_type == 'alerts':
                await show_alert_setup(query, user.id)
            elif menu_type == 'digest':
                await show_digest_menu(query, user.id)
            elif menu_type == 'settings':
                await language_command_from_callback(query, user.id)
        # Tutorial callbacks
        elif callback_data.startswith('tutorial_'):
            await handle_tutorial_callback(query, user.id, callback_data)
        # Search callbacks
        elif callback_data.startswith('search_'):
            await handle_search_callback(query, user.id, callback_data)
        elif callback_data.startswith('collections_page_'):
            page = int(callback_data.replace('collections_page_', ''))
            await show_popular_collections(query, user.id, page)
            
    except Exception as e:
        logger.error(f"Error in quick_actions_callback: {e}")
        try:
            error_message = get_text(update.effective_user.id, 'errors.general')
            await query.edit_message_text(error_message)
        except:
            pass


# Search Callback Handlers
async def handle_search_callback(query, user_id: int, callback_data: str) -> None:
    """Handle advanced search callbacks"""
    try:
        if callback_data == 'search_quick':
            await show_quick_search_input(query, user_id)
        elif callback_data == 'search_filters':
            await show_search_filters_menu(query, user_id)
        elif callback_data == 'search_suggestions':
            await show_search_suggestions(query, user_id)
        elif callback_data == 'search_history':
            await show_search_history(query, user_id)
        elif callback_data == 'search_clear_filters':
            await clear_search_filters(query, user_id)
        elif callback_data.startswith('search_filter_'):
            filter_type = callback_data.replace('search_filter_', '')
            await handle_filter_selection(query, user_id, filter_type)
        elif callback_data.startswith('search_suggestion_'):
            suggestion = callback_data.replace('search_suggestion_', '')
            await perform_advanced_search(query, user_id, suggestion)
        elif callback_data.startswith('search_history_'):
            history_query = callback_data.replace('search_history_', '')
            await perform_advanced_search(query, user_id, history_query)
    except Exception as e:
        logger.error(f"Error in search callback: {e}")
        error_text = get_text(user_id, 'advanced_search.error')
        await query.edit_text(error_text, parse_mode='Markdown')


async def show_search_no_results(message_or_query, user_id: int, query: str) -> None:
    """Show no results message with suggestions."""
    text = get_text(user_id, 'advanced_search.no_results', query=query)
    
    # Get suggestions
    suggestions = get_search_suggestions(user_id)
    if suggestions:
        text += f"\n\n💡 **{get_text(user_id, 'advanced_search.try_suggestions')}:**\n"
        for suggestion in suggestions[:3]:
            text += f"• {suggestion}\n"
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, 'advanced_search.search_again'), callback_data="search_quick"),
            InlineKeyboardButton(get_text(user_id, 'advanced_search.suggestions'), callback_data="search_suggestions")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(message_or_query, 'edit_text'):
        await message_or_query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await message_or_query.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_search_results(message_or_query, user_id: int, collection_data: Dict[str, Any], query: str) -> None:
    """Show search results with collection information."""
    # Extract relevant information from the API response
    stats = collection_data.get('stats', {})
    details = collection_data.get('details', {})
    
    name = details.get('name', 'Unknown')
    slug = details.get('slug', '')
    
    # Floor price information
    floor_info = stats.get('floorInfo', {})
    floor_price_eth = floor_info.get('currentFloorNative', 0)
    floor_price_usd = floor_info.get('currentFloorUsd', 0)
    
    # Create result message
    text = f"🔍 **{get_text(user_id, 'advanced_search.results_for', query=query)}**\n\n"
    text += f"📊 **{name}**\n"
    text += f"💰 Floor: {floor_price_eth:.4f} ETH (${floor_price_usd:.2f})\n"
    
    # Add volume and other stats if available
    sales_temp_native = stats.get('salesTemporalityNative', {})
    volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
    if volume_24h > 0:
        text += f"📈 24h Volume: {volume_24h:.2f} ETH\n"
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, 'price.view_details'), url=f"https://nftpricefloor.com/collection/{slug}"),
            InlineKeyboardButton(get_text(user_id, 'alerts.setup'), callback_data=f"alert_{slug}")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'advanced_search.search_again'), callback_data="search_quick"),
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(message_or_query, 'edit_text'):
        await message_or_query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await message_or_query.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


# Tutorial Callback Handlers
async def handle_tutorial_callback(query, user_id: int, callback_data: str) -> None:
    """Handle interactive tutorial callbacks"""
    try:
        if callback_data == 'tutorial_step_1':
            await show_tutorial_step_1(query, user_id)
        elif callback_data == 'tutorial_step_2':
            await show_tutorial_step_2(query, user_id)
        elif callback_data == 'tutorial_step_3':
            await show_tutorial_step_3(query, user_id)
        elif callback_data == 'tutorial_step_4':
            await show_tutorial_step_4(query, user_id)
        elif callback_data == 'tutorial_skip':
            await skip_tutorial(query, user_id)
        elif callback_data == 'tutorial_try_price':
            await tutorial_try_price(query, user_id)
        elif callback_data == 'tutorial_try_rankings':
            await tutorial_try_rankings(query, user_id)
        elif callback_data == 'tutorial_try_alerts':
            await tutorial_try_alerts(query, user_id)
        elif callback_data == 'tutorial_try_language':
            await tutorial_try_language(query, user_id)
        elif callback_data == 'tutorial_finish':
            await finish_tutorial(query, user_id)
        elif callback_data.startswith('tutorial_continue_'):
            step = callback_data.replace('tutorial_continue_', '')
            if step == '2':
                await show_tutorial_step_2(query, user_id)
            elif step == '3':
                await show_tutorial_step_3(query, user_id)
            elif step == '4':
                await show_tutorial_step_4(query, user_id)
            elif step == 'final':
                await show_tutorial_final(query, user_id)
    except Exception as e:
        logger.error(f"Error in handle_tutorial_callback: {e}")
        await query.edit_message_text(get_text(user_id, 'errors.general'))

async def show_tutorial_step_1(query, user_id: int) -> None:
    """Show tutorial step 1 - Floor Price"""
    mark_tutorial_step_completed(user_id, 1)
    
    message = f"{get_text(user_id, 'tutorial.interactive.step1_title')}\n\n{get_text(user_id, 'tutorial.interactive.step1_desc')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.try_feature'), callback_data='tutorial_try_price')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.next_step'), callback_data='tutorial_continue_2')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.skip_tutorial'), callback_data='tutorial_skip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_tutorial_step_2(query, user_id: int) -> None:
    """Show tutorial step 2 - Rankings"""
    mark_tutorial_step_completed(user_id, 2)
    
    message = f"{get_text(user_id, 'tutorial.interactive.step2_title')}\n\n{get_text(user_id, 'tutorial.interactive.step2_desc')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.try_feature'), callback_data='tutorial_try_rankings')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.next_step'), callback_data='tutorial_continue_3')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.skip_tutorial'), callback_data='tutorial_skip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_tutorial_step_3(query, user_id: int) -> None:
    """Show tutorial step 3 - Alerts"""
    mark_tutorial_step_completed(user_id, 3)
    
    message = f"{get_text(user_id, 'tutorial.interactive.step3_title')}\n\n{get_text(user_id, 'tutorial.interactive.step3_desc')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.try_feature'), callback_data='tutorial_try_alerts')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.next_step'), callback_data='tutorial_continue_4')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.skip_tutorial'), callback_data='tutorial_skip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_tutorial_step_4(query, user_id: int) -> None:
    """Show tutorial step 4 - Language & Settings"""
    mark_tutorial_step_completed(user_id, 4)
    
    message = f"{get_text(user_id, 'tutorial.interactive.step4_title')}\n\n{get_text(user_id, 'tutorial.interactive.step4_desc')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.try_feature'), callback_data='tutorial_try_language')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.next_step'), callback_data='tutorial_continue_final')],
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.skip_tutorial'), callback_data='tutorial_skip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_tutorial_final(query, user_id: int) -> None:
    """Show tutorial completion"""
    message = f"{get_text(user_id, 'tutorial.interactive.final_title')}\n\n{get_text(user_id, 'tutorial.interactive.final_desc')}"
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.finish_tutorial'), callback_data='tutorial_finish')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def tutorial_try_price(query, user_id: int) -> None:
    """Let user try the price feature during tutorial"""
    await get_collection_price_from_callback(query, user_id, 'cryptopunks')
    
    # After showing price, show step completion
    await asyncio.sleep(2)
    message = get_text(user_id, 'tutorial.interactive.step1_completed')
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.continue'), callback_data='tutorial_continue_2')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    except:
        pass

async def tutorial_try_rankings(query, user_id: int) -> None:
    """Let user try the rankings feature during tutorial"""
    await rankings_command_from_callback(query, user_id)
    
    # After showing rankings, show step completion
    await asyncio.sleep(2)
    message = get_text(user_id, 'tutorial.interactive.step2_completed')
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.continue'), callback_data='tutorial_continue_3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    except:
        pass

async def tutorial_try_alerts(query, user_id: int) -> None:
    """Let user try the alerts feature during tutorial"""
    await show_alert_setup(query, user_id)
    
    # After showing alerts, show step completion
    await asyncio.sleep(2)
    message = get_text(user_id, 'tutorial.interactive.step3_completed')
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.continue'), callback_data='tutorial_continue_4')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    except:
        pass

async def tutorial_try_language(query, user_id: int) -> None:
    """Let user try the language feature during tutorial"""
    await language_command_from_callback(query, user_id)
    
    # After showing language options, show step completion
    await asyncio.sleep(2)
    message = get_text(user_id, 'tutorial.interactive.step4_completed')
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'tutorial.interactive.continue'), callback_data='tutorial_continue_final')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    except:
        pass

async def skip_tutorial(query, user_id: int) -> None:
    """Skip the tutorial and go to main menu"""
    mark_tutorial_completed(user_id)
    log_user_action(user_id, 'tutorial_skipped', {})
    
    # Show main menu
    await show_main_menu(query, user_id)

async def finish_tutorial(query, user_id: int) -> None:
    """Complete the tutorial and go to main menu"""
    mark_tutorial_completed(user_id)
    log_user_action(user_id, 'tutorial_completed', {})
    
    # Show main menu
    await show_main_menu(query, user_id)

async def show_quick_search_input(query, user_id: int) -> None:
    """Show quick search input prompt."""
    text = get_text(user_id, 'advanced_search.quick_search_prompt')
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_search_filters_menu(query, user_id: int) -> None:
    """Show search filters menu."""
    text = get_text(user_id, 'advanced_search.filters_menu')
    
    # Get current filters
    current_filters = get_user_search_filters(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"📂 {get_text(user_id, 'advanced_search.filter_category')} {'✓' if current_filters.get('category') else ''}",
                callback_data="search_filter_category"
            )
        ],
        [
            InlineKeyboardButton(
                f"💰 {get_text(user_id, 'advanced_search.filter_price')} {'✓' if current_filters.get('min_price') or current_filters.get('max_price') else ''}",
                callback_data="search_filter_price"
            )
        ],
        [
            InlineKeyboardButton(
                f"🔥 {get_text(user_id, 'advanced_search.filter_trending')} {'✓' if current_filters.get('trending') else ''}",
                callback_data="search_filter_trending"
            ),
            InlineKeyboardButton(
                f"💎 {get_text(user_id, 'advanced_search.filter_blue_chip')} {'✓' if current_filters.get('blue_chip') else ''}",
                callback_data="search_filter_blue_chip"
            )
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'advanced_search.clear_filters'), callback_data="search_clear_filters")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_search_suggestions(query, user_id: int) -> None:
    """Show search suggestions."""
    text = get_text(user_id, 'advanced_search.suggestions_title')
    
    suggestions = get_search_suggestions(user_id)
    
    keyboard = []
    for i, suggestion in enumerate(suggestions[:6]):
        keyboard.append([
            InlineKeyboardButton(f"🔍 {suggestion}", callback_data=f"search_suggestion_{suggestion}")
        ])
    
    keyboard.append([
        InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_search_history(query, user_id: int) -> None:
    """Show user's search history."""
    text = get_text(user_id, 'advanced_search.history_title')
    
    history = get_user_search_history(user_id)
    
    if not history:
        text += f"\n\n{get_text(user_id, 'advanced_search.no_history')}"
        keyboard = [
            [
                InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
            ]
        ]
    else:
        keyboard = []
        for search_query in history[:6]:
            keyboard.append([
                InlineKeyboardButton(f"🔍 {search_query}", callback_data=f"search_history_{search_query}")
            ])
        
        keyboard.append([
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_menu")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def clear_search_filters(query, user_id: int) -> None:
    """Clear all user search filters."""
    clear_user_search_filters(user_id)
    
    text = get_text(user_id, 'advanced_search.filters_cleared')
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="search_filters")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_filter_selection(query, user_id: int, filter_type: str) -> None:
    """Handle filter selection and toggle."""
    current_filters = get_user_search_filters(user_id)
    
    if filter_type == 'trending':
        current_filters['trending'] = not current_filters.get('trending', False)
    elif filter_type == 'blue_chip':
        current_filters['blue_chip'] = not current_filters.get('blue_chip', False)
    elif filter_type == 'category':
        # For now, just toggle between 'art' and None
        if current_filters.get('category') == 'art':
            current_filters.pop('category', None)
        else:
            current_filters['category'] = 'art'
    elif filter_type == 'price':
        # For now, set a default price range
        if current_filters.get('min_price'):
            current_filters.pop('min_price', None)
            current_filters.pop('max_price', None)
        else:
            current_filters['min_price'] = 0.1
            current_filters['max_price'] = 10.0
    
    set_user_search_filters(user_id, current_filters)
    
    # Show updated filters menu
    await show_search_filters_menu(query, user_id)


async def show_collection_search(query, user_id: int) -> None:
    """
    Show collection search interface with input instructions.
    """
    try:
        search_text = get_text(user_id, 'search.instructions')
        back_button_text = get_text(user_id, 'navigation.back')
        
        keyboard = [
            [InlineKeyboardButton(back_button_text, callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            search_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in show_collection_search: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def show_quick_access_collections(query, user_id: int) -> None:
    """
    Show quick access to frequently used collections.
    """
    try:
        # Define quick access collections (top 10 most popular)
        quick_collections = [
            {'name': 'Bored Ape Yacht Club', 'slug': 'boredapeyachtclub'},
            {'name': 'CryptoPunks', 'slug': 'cryptopunks'},
            {'name': 'Mutant Ape Yacht Club', 'slug': 'mutant-ape-yacht-club'},
            {'name': 'Azuki', 'slug': 'azuki'},
            {'name': 'CloneX', 'slug': 'clonex'},
            {'name': 'Doodles', 'slug': 'doodles-official'},
            {'name': 'Cool Cats', 'slug': 'cool-cats-nft'},
            {'name': 'World of Women', 'slug': 'world-of-women-nft'},
            {'name': 'VeeFriends', 'slug': 'veefriends'},
            {'name': 'Art Blocks Curated', 'slug': 'art-blocks'}
        ]
        
        quick_access_text = get_text(user_id, 'quick_access.title')
        back_button_text = get_text(user_id, 'navigation.back')
        
        keyboard = []
        
        # Add collection buttons in pairs
        for i in range(0, len(quick_collections), 2):
            row = []
            for j in range(2):
                if i + j < len(quick_collections):
                    collection = quick_collections[i + j]
                    row.append(InlineKeyboardButton(
                        f"⚡ {collection['name']}",
                        callback_data=f"collection_{collection['slug']}"
                    ))
            keyboard.append(row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton(back_button_text, callback_data='main_menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            quick_access_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in show_quick_access_collections: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def show_popular_collections(query, user_id: int, page: int = 0) -> None:
    """
    Display popular NFT collections with visual indicators and pagination.
    """
    try:
        # Get curated collections from translations
        title = get_text(user_id, 'popular_collections.title')
        subtitle = get_text(user_id, 'popular_collections.subtitle')
        
        # Get all curated collections from translation file
        curated_collections = [
            'cryptopunks', 'bored-ape-yacht-club', 'mutant-ape-yacht-club', 'azuki', 'doodles-official',
            'otherdeed-for-otherdeeds', 'clonex', 'moonbirds', 'veefriends', 'world-of-women-nft',
            'cool-cats-nft', 'pudgypenguins', 'artblocks-curated', 'chromie-squiggle-by-snowfro', 'meebits',
            'sandbox', 'decentraland', 'cryptokitties', 'loot-for-adventurers', 'ens',
            'goblintown-wtf', 'proof-moonbirds', 'hashmasks', 'cyberkongz', 'deadfellaz',
            'lazy-lions', 'creature-world-nft', 'gutter-cat-gang', '0n1-force', 'superlative-apes'
        ]
        
        # Pagination settings
        items_per_page = 5
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_collections = curated_collections[start_idx:end_idx]
        
        collections_text = f"**{title}**\n{subtitle}\n\n"
        
        keyboard = []
        for slug in page_collections:
            # Get collection data from translations
            name = get_text(user_id, f'popular_collections.curated_list.{slug}.name')
            description = get_text(user_id, f'popular_collections.curated_list.{slug}.description')
            tags = get_text(user_id, f'popular_collections.curated_list.{slug}.tags')
            
            # Format visual indicators based on tags
            visual_indicators = []
            if isinstance(tags, list):
                for tag in tags:
                    tag_text = get_text(user_id, f'popular_collections.tags.{tag}')
                    if tag_text:
                        visual_indicators.append(tag_text)
            
            indicators_str = ' '.join(visual_indicators) if visual_indicators else ''
            
            collections_text += f"**{name}** {indicators_str}\n{description}\n\n"
            
            # Add collection button that shows full price information
            keyboard.append([
                InlineKeyboardButton(f"🎨 {name}", callback_data=f'collection_{slug}')
            ])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'popular_page_{page-1}'))
        if end_idx < len(curated_collections):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f'popular_page_{page+1}'))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Add search button
        keyboard.append([
            InlineKeyboardButton("🔍 Search Collections", callback_data='search_collections')
        ])
        
        # Add menu navigation
        keyboard.append([
            InlineKeyboardButton("🏆 Rankings", callback_data='quick_rankings'),
            InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')
        ])
        
        # Add page indicator
        total_pages = (len(curated_collections) + items_per_page - 1) // items_per_page
        collections_text += f"\n📄 Page {page + 1} of {total_pages}"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(collections_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_popular_collections: {e}")
        error_message = get_text(user_id, 'errors.api_error')
        await query.edit_message_text(error_message)


async def show_tutorial(query, user_id: int) -> None:
    """
    Display interactive tutorial for new users.
    """
    try:
        tutorial_text = get_text(user_id, 'welcome.tutorial.title')
        tutorial_text += get_text(user_id, 'welcome.tutorial.step1') + "\n\n"
        tutorial_text += get_text(user_id, 'welcome.tutorial.step2') + "\n\n"
        tutorial_text += get_text(user_id, 'welcome.tutorial.step3') + "\n\n"
        tutorial_text += get_text(user_id, 'welcome.tutorial.step4') + "\n\n"
        tutorial_text += get_text(user_id, 'welcome.tutorial.complete')
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Try Price Check", callback_data='quick_popular'),
                InlineKeyboardButton("🏆 View Rankings", callback_data='quick_rankings')
            ],
            [
                InlineKeyboardButton("🔔 Set Alert", callback_data='quick_alert'),
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='main_menu')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(tutorial_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_tutorial: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_main_menu(query, user_id: int) -> None:
    """
    Display the unified main menu with all core features matching the specified design.
    """
    try:
        # Get user info for personalized greeting
        user_name = "Dave Joga"
        if hasattr(query, 'from_user') and query.from_user:
            user_name = query.from_user.first_name or "Dave Joga"
        
        # Create the welcome message matching the image design
        welcome_message = f"🤖 Hello {user_name}!\n\nWelcome to NFT Market Insights Bot! I'm here to help you track NFT collections, set price alerts, and stay updated with the latest market trends.\n\n✨ **Let's get you started:**\n\n🎯 **Quick Actions:**\n• 💰 Check floor prices\n• 🏆 Browse top collections\n• 🔔 Set price alerts\n• 🌍 Change language\n\nChoose an option below or use /help for all commands!"
        
        # Use the standardized main menu keyboard
        keyboard = get_main_menu_keyboard(user_id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


# Removed show_start_menu - now using unified show_main_menu


async def show_tutorial_menu(query, user_id: int) -> None:
    """
    Display the tutorial and help options.
    """
    try:
        menu_text = "📚 **Tutorial & Help**\n\nLearn how to use the bot:"
        
        keyboard = [
            [
                InlineKeyboardButton('📚 Start Tutorial', callback_data='main_tutorial'),
                InlineKeyboardButton('❓ Help Topics', callback_data='main_help')
            ],
            [
                InlineKeyboardButton('🔙 Back to Main Menu', callback_data='back_to_main')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_tutorial_menu: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_help_menu(query, user_id: int) -> None:
    """
    Display enhanced help menu with examples.
    """
    try:
        help_text = get_text(user_id, 'help.title') + "\n\n"
        
        # Add command examples
        commands = get_text(user_id, 'help.commands')
        for cmd, desc in commands.items():
            help_text += f"{cmd} - {desc}\n"
        
        help_text += "\n" + get_text(user_id, 'help.usage')
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Price Help", callback_data='help_price'),
                InlineKeyboardButton("🏆 Rankings Help", callback_data='help_rankings')
            ],
            [
                InlineKeyboardButton("🔔 Alerts Help", callback_data='help_alerts'),
                InlineKeyboardButton("🎓 Tutorial", callback_data='quick_tutorial')
            ],
            [
                InlineKeyboardButton("💰 Try Price Check", callback_data='quick_popular'),
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='main_menu')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_help_menu: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_price_help(query, user_id: int) -> None:
    """
    Display detailed help for the price command.
    """
    try:
        help_data = get_text(user_id, 'help.detailed.price_help')
        
        help_text = f"{help_data['title']}\n\n"
        help_text += f"{help_data['description']}\n\n"
        help_text += f"{help_data['usage']}\n\n"
        
        # Add examples
        for example in help_data['examples']:
            help_text += f"{example}\n"
        help_text += "\n"
        
        # Add tips
        for tip in help_data['tips']:
            help_text += f"{tip}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Try Price Check", callback_data='quick_popular'),
                InlineKeyboardButton("🏆 Other Help", callback_data='quick_help')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='quick_help')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_price_help: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_rankings_help(query, user_id: int) -> None:
    """
    Display detailed help for the rankings command.
    """
    try:
        help_data = get_text(user_id, 'help.detailed.rankings_help')
        
        help_text = f"{help_data['title']}\n\n"
        help_text += f"{help_data['description']}\n\n"
        help_text += f"{help_data['usage']}\n\n"
        
        # Add examples
        for example in help_data['examples']:
            help_text += f"{example}\n"
        help_text += "\n"
        
        # Add tips
        for tip in help_data['tips']:
            help_text += f"{tip}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🏆 Try Rankings", callback_data='quick_rankings'),
                InlineKeyboardButton("💰 Other Help", callback_data='quick_help')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='quick_help')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_rankings_help: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_alerts_help(query, user_id: int) -> None:
    """
    Display detailed help for the alerts command.
    """
    try:
        help_data = get_text(user_id, 'help.detailed.alerts_help')
        
        help_text = f"{help_data['title']}\n\n"
        help_text += f"{help_data['description']}\n\n"
        help_text += f"{help_data['usage']}\n\n"
        
        # Add examples
        for example in help_data['examples']:
            help_text += f"{example}\n"
        help_text += "\n"
        
        # Add tips
        for tip in help_data['tips']:
            help_text += f"{tip}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔔 Try Alerts", callback_data='quick_alert'),
                InlineKeyboardButton("💰 Other Help", callback_data='quick_help')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='quick_help')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_alerts_help: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)


async def show_alert_setup(query, user_id: int) -> None:
    """
    Display alert setup options with enhanced visual indicators.
    """
    try:
        alert_text = f"🔔 {get_text(user_id, 'alerts.help')}"
        
        keyboard = [
            [
                InlineKeyboardButton("📋 View My Alerts", callback_data='alerts_list'),
                InlineKeyboardButton("⚡ Quick Setup", callback_data='quick_popular')
            ],
            [
                InlineKeyboardButton("📰 Daily Digest", callback_data='menu_digest')
            ],
            [
                InlineKeyboardButton(f"🏠 {get_text(user_id, 'common.back')}", callback_data='main_menu')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(alert_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_alert_setup: {e}")
        error_message = f"❌ {get_text(user_id, 'errors.general')}"
        await query.edit_message_text(error_message)


async def language_command_from_callback(query, user_id: int) -> None:
    """
    Handle language selection from callback.
    """
    try:
        language_text = get_text(user_id, 'language.select')
        keyboard_options = get_language_options_keyboard()
        
        # Arrange buttons in rows (2 per row)
        keyboard = []
        for i in range(0, len(keyboard_options), 2):
            row = []
            for j in range(i, min(i + 2, len(keyboard_options))):
                row.append(keyboard_options[j])
            keyboard.append(row)
        
        # Add back button
        back_button_text = get_text(user_id, 'navigation.back')
        keyboard.append([InlineKeyboardButton(back_button_text, callback_data='main_menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(language_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in language_command_from_callback: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def rankings_command_from_callback(query, user_id: int) -> None:
    """
    Handle rankings command from callback.
    """
    try:
        loading_message = get_text(user_id, 'rankings.loading')
        await query.edit_message_text(loading_message)
        
        # Fetch rankings data
        rankings_data = await fetch_rankings_cached(offset=0, limit=10)
        
        if not rankings_data:
            error_message = get_text(user_id, 'rankings.error')
            await query.edit_message_text(error_message)
            return
        
        # fetch_rankings_cached returns a list directly
        projects = rankings_data if isinstance(rankings_data, list) else []
        if not projects:
            no_data_message = get_text(user_id, 'rankings.no_data')
            await query.edit_message_text(no_data_message)
            return
        
        # Format rankings message
        rankings_text = get_text(user_id, 'rankings.title')
        
        for i, project in enumerate(projects[:10], 1):
            name = project.get('name', 'Unknown')
            slug = project.get('slug', '')
            stats = project.get('stats', {})
            floor_info = stats.get('floorInfo', {})
            
            floor_price_eth = floor_info.get('currentFloorNative', 0)
            floor_price_usd = floor_info.get('currentFloorUsd', 0)
            
            # Get 24h price change from floorTemporalityUsd and floorTemporalityNative
            floor_temp_usd = stats.get('floorTemporalityUsd', {})
            floor_temp_native = stats.get('floorTemporalityNative', {})
            price_change_24h = floor_temp_native.get('diff24h', 0)
            price_change_24h_usd = floor_temp_usd.get('diff24h', 0)
            
            # Get 24h volume and sales count
            volume_data = stats.get('volume', {})
            count_data = stats.get('count', {})
            sales_temp_native = stats.get('salesTemporalityNative', {})
            volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
            sales_24h = count_data.get('val24h', 0)
            sales_count_native = sales_temp_native.get('count', {}).get('val24h', 0)
            
            # Format 24h price change
            if price_change_24h:
                sign = "+" if price_change_24h >= 0 else ""
                price_change_native = f"{sign}{price_change_24h:.1f}%"
                price_change_usd = f"({sign}{price_change_24h_usd:.1f}%)"
                price_change_display = f"{price_change_native} {price_change_usd}"
            else:
                price_change_display = "N/A"
            
            # Format floor price in ETH and USD
            floor_eth = f"{floor_price_eth:.1f} ETH" if floor_price_eth else "N/A"
            floor_usd = f"(${floor_price_usd:,.0f})" if floor_price_usd else "(N/A)"
            floor_display = f"{floor_eth} {floor_usd}" if floor_price_eth and floor_price_usd else "N/A"
            
            # Format 24h volume and sales
            vol_24h = f"{volume_24h:.1f} ETH" if volume_24h else "N/A"
            sales_count_display = f"{int(sales_24h)} sales" if sales_24h else "0 sales"
            volume_sales_display = f"{vol_24h} ({sales_count_display})" if volume_24h else "N/A"
            
            # Create hyperlink for collection name
            collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
            
            rankings_text += (
                f"{i}. {collection_link}\n"
                f"    📈 24h Change: {price_change_display}\n"
                f"    🏠 Floor: {floor_display}\n"
                f"    📊 24h Volume: {volume_sales_display}\n\n"
            )
        
        rankings_text += "\n" + get_text(user_id, 'rankings.footer')
        
        # Add navigation buttons
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'rankings.next_button'), callback_data='rankings_next_10')],
            [InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(rankings_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in rankings_command_from_callback: {e}")
        error_message = get_text(user_id, 'rankings.error')
        await query.edit_message_text(error_message)


async def show_top_sales_from_callback(query, user_id: int) -> None:
    """
    Handle top sales command from callback.
    """
    try:
        loading_message = get_text(user_id, 'top_sales.loading')
        await query.edit_message_text(loading_message)
        
        # Fetch top sales data
        top_sales_data = await fetch_top_sales_cached()
        
        if not top_sales_data:
            error_message = get_text(user_id, 'top_sales.error')
            await query.edit_message_text(error_message)
            return
        
        # Format top sales message
        message = await format_top_sales_message(top_sales_data, user_id)
        
        # Add navigation buttons
        keyboard = get_top_sales_keyboard(user_id)
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_top_sales_from_callback: {e}")
        error_message = get_text(user_id, 'top_sales.error')
        await query.edit_message_text(error_message)


async def get_collection_price_from_callback(query, user_id: int, collection_slug: str) -> None:
    """
    Get collection price from callback button.
    This function displays identical information to the /price command.
    """
    try:
        searching_message = get_text(user_id, 'price.searching', collection=collection_slug)
        await query.edit_message_text(searching_message)
        
        # Fetch detailed project data using the projects/{slug} endpoint (same as /price command)
        project_data = await fetch_nftpf_project_by_slug_cached(collection_slug)
        
        if not project_data:
            not_found_message = get_text(user_id, 'price.not_found', collection=collection_slug)
            keyboard = [[InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(not_found_message, reply_markup=reply_markup)
            return
        
        # Extract data from the detailed project response (same as /price command)
        stats = project_data.get('stats', {})
        details = project_data.get('details', {})
        
        name = details.get('name', 'Unknown')
        
        # Floor price information from stats
        floor_info = stats.get('floorInfo', {})
        floor_price_eth = floor_info.get('currentFloorNative', 0)
        floor_price_usd = floor_info.get('currentFloorUsd', 0)
        
        # 24h change from floor temporality
        floor_temporality = stats.get('floorTemporalityUsd', {})
        change_24h = floor_temporality.get('diff24h', 0)
        
        # Volume and sales data from sales temporality
        sales_temporality = stats.get('salesTemporalityUsd', {})
        volume_data = sales_temporality.get('volume', {})
        count_data = sales_temporality.get('count', {})
        average_data = sales_temporality.get('average', {})
        
        volume_24h_usd = volume_data.get('val24h', 0)
        sales_24h = count_data.get('val24h', 0)
        avg_sale_price_usd = average_data.get('val24h', 0)
        
        # Convert volume from USD to ETH (approximate)
        volume_24h_eth = volume_24h_usd / floor_price_usd if floor_price_usd > 0 else 0
        avg_sale_price_eth = avg_sale_price_usd / floor_price_usd * floor_price_eth if floor_price_usd > 0 and floor_price_eth > 0 else 0
        
        # Supply information from stats
        total_supply = stats.get('totalSupply', 0)
        listed_count = stats.get('listedCount', 0)
        
        # Official links from social media
        social_media = details.get('socialMedia', [])
        website = ''
        twitter = ''
        discord = ''
        
        for social in social_media:
            if social.get('name') == 'website':
                website = social.get('url', '')
            elif social.get('name') == 'twitter':
                twitter = social.get('url', '')
            elif social.get('name') == 'discord':
                discord = social.get('url', '')
        
        # Create hyperlink for collection name
        slug = details.get('slug', '')
        collection_link = f"https://nftpricefloor.com/collection/{slug}"
        
        # Format the response text to match /price command exactly
        response_text = f"📊 **{name}**\n\n"
        
        if floor_price_eth > 0:
            response_text += f"💎 **Floor Price:** {floor_price_eth:.4f} ETH (${floor_price_usd:,.2f})\n"
        else:
            response_text += f"💎 **Floor Price:** Not available\n"
        
        # 24h change
        if change_24h != 0:
            change_emoji = "📈" if change_24h > 0 else "📉"
            response_text += f"{change_emoji} **24h Change:** {change_24h:+.2f}%\n"
        else:
            response_text += f"📊 **24h Change:** 0.0%\n"
        
        # Volume
        if volume_24h_eth > 0:
            response_text += f"💰 **Volume:** {volume_24h_eth:.2f} ETH (${volume_24h_usd:,.0f})\n"
        else:
            response_text += f"💰 **Volume:** 0 ETH (0 sales)\n"
        
        # Listings
        if listed_count > 0:
            response_text += f"🏷️ **Listings:** {listed_count:,}\n"
        else:
            response_text += f"🏷️ **Listings:** 0\n"
        
        # Average sale price
        if avg_sale_price_eth > 0:
            response_text += f"📊 **Average Sale:** {avg_sale_price_eth:.4f} ETH (${avg_sale_price_usd:,.2f})\n"
        else:
            response_text += f"📊 **Average Sale:** No recent sales\n"
        
        # Social media links
        if website or twitter or discord:
            response_text += "\n🔗 **Official Links:**\n"
            if website:
                response_text += f"• [Website]({website})\n"
            if twitter:
                response_text += f"• [Twitter]({twitter})\n"
            if discord:
                response_text += f"• [Discord]({discord})\n"
        
        response_text += f"\n🔗 [View Chart & Analytics]({collection_link})\n"
        response_text += f"\n📊 Data from NFTPriceFloor API"
        
        keyboard = [
            [
                InlineKeyboardButton("🔔 Set Alert", callback_data=f'alert_{collection_slug}'),
                InlineKeyboardButton("🔗 View Details", url=f"https://nftpricefloor.com/{slug}?=tbot")
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        logger.info(f"Price callback used for collection '{collection_slug}' by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in get_collection_price_from_callback: {e}")
        error_message = get_text(user_id, 'price.error')
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(error_message, reply_markup=reply_markup)


async def show_collection_actions(query, user_id: int, collection_slug: str) -> None:
    """
    Show action options for a specific collection.
    """
    try:
        # Get collection info from translations
        collection_name = get_text(user_id, f'popular_collections.curated_list.{collection_slug}.name')
        collection_desc = get_text(user_id, f'popular_collections.curated_list.{collection_slug}.description')
        collection_tags = get_text(user_id, f'popular_collections.curated_list.{collection_slug}.tags')
        
        if not collection_name or collection_name.startswith('popular_collections.'):
            collection_name = collection_slug.replace('_', ' ').title()
            collection_desc = "Popular NFT collection"
            collection_tags = "🔥 trending"
        
        action_text = f"🎨 **{collection_name}**\n\n"
        action_text += f"📝 {collection_desc}\n\n"
        action_text += f"🏷️ {collection_tags}\n\n"
        action_text += "**Choose an action:**"
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Check Price", callback_data=f'price_{collection_slug}'),
                InlineKeyboardButton("🔔 Set Alert", callback_data=f'alert_{collection_slug}')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(action_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_collection_actions: {e}")
        error_message = get_text(user_id, 'errors.general')
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(error_message, reply_markup=reply_markup)


async def setup_alert_from_callback(query, user_id: int, collection_slug: str) -> None:
    """
    Setup alert from callback button.
    """
    try:
        alert_text = f"🔔 **Set Price Alert**\n\n"
        alert_text += f"Collection: **{collection_slug}**\n\n"
        alert_text += "To set an alert, use the command:\n"
        alert_text += f"`/alerts add {collection_slug} [target_price]`\n\n"
        alert_text += "**Example:**\n"
        alert_text += f"`/alerts add {collection_slug} 50`\n\n"
        alert_text += "💡 *This will notify you when the floor price reaches 50 ETH*"
        
        keyboard = [
            [
                InlineKeyboardButton("📋 View My Alerts", callback_data='alerts_list'),
                InlineKeyboardButton("💰 Check Price", callback_data=f'price_{collection_slug}')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(alert_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in setup_alert_from_callback: {e}")
        error_message = get_text(user_id, 'errors.general')
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(error_message, reply_markup=reply_markup)


# Import user storage module
from user_storage import (
    get_digest_settings, set_digest_settings, toggle_digest_enabled, 
    set_digest_time, init_storage, cleanup_storage,
    is_tutorial_completed, start_tutorial, mark_tutorial_step_completed, 
    mark_tutorial_completed, get_user_tutorial_status
)
# Import search storage module
from search_storage import (
    init_search_storage, add_search_to_history, get_user_search_history,
    get_search_suggestions, set_user_search_filters, get_user_search_filters,
    clear_user_search_filters, categorize_collection, cleanup_search_storage
)
from digest_scheduler import start_digest_scheduler, stop_digest_scheduler
# Removed direct import - using cached version from cached_api

async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /digest command.
    Shows digest settings and allows users to toggle on/off.
    """
    try:
        user = update.effective_user
        log_user_action(user.id, "digest_command", "initiated")
        await show_digest_menu(update.message, user.id)
        log_user_action(user.id, "digest_command", "success")
    except Exception as e:
        await handle_command_error(update, e, user.id)

async def digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle digest-related callback queries.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        callback_data = query.data
        
        if callback_data == 'digest_toggle':
            await toggle_digest(query, user.id)
        elif callback_data == 'digest_set_time':
            await show_digest_time_selection(query, user.id)
        elif callback_data.startswith('digest_time_'):
            time_str = callback_data.replace('digest_time_', '')
            await handle_set_digest_time(query, user.id, time_str)
        elif callback_data == 'digest_preview':
            await show_digest_preview(query, user.id)
        elif callback_data == 'digest_settings':
            await show_digest_settings(query, user.id)
        elif callback_data == 'digest_menu':
            await show_digest_menu(query, user.id)
            
    except Exception as e:
        # For callback queries, we need to handle errors differently
        from error_handler import get_error_message
        error_message = get_error_message(update.effective_user.id, e)
        await query.edit_message_text(error_message)
        logger.error(f"Error in digest_callback for user {update.effective_user.id}: {type(e).__name__}: {e}", exc_info=True)

async def show_digest_menu(message_or_query, user_id: int) -> None:
    """
    Display the digest menu with current status and options.
    """
    try:
        # Get current digest settings
        user_settings = get_digest_settings(user_id)
        
        if user_settings['enabled']:
            status_text = get_text(user_id, 'digest.status_enabled', time=user_settings['time'])
            toggle_button_text = get_text(user_id, 'digest.buttons.disable')
        else:
            status_text = get_text(user_id, 'digest.status_disabled')
            toggle_button_text = get_text(user_id, 'digest.buttons.enable')
        
        keyboard = [
            [InlineKeyboardButton(toggle_button_text, callback_data='digest_toggle')],
            [InlineKeyboardButton(get_text(user_id, 'digest.buttons.set_time'), callback_data='digest_set_time')],
            [InlineKeyboardButton(get_text(user_id, 'digest.buttons.preview'), callback_data='digest_preview')],
            [InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await message_or_query.reply_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in show_digest_menu: {e}")
        error_message = get_text(user_id, 'errors.general')
        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(error_message)
        else:
            await message_or_query.reply_text(error_message)

async def toggle_digest(query, user_id: int) -> None:
    """
    Toggle digest on/off for the user.
    """
    try:
        enabled = toggle_digest_enabled(user_id)
        user_settings = get_digest_settings(user_id)
        
        if enabled:
            message = get_text(user_id, 'digest.toggle_on', time=user_settings['time'])
        else:
            message = get_text(user_id, 'digest.toggle_off')
        
        await query.edit_message_text(message, parse_mode='Markdown')
        
        # Show menu again after a brief delay
        await asyncio.sleep(2)
        await show_digest_menu(query, user_id)
        
    except Exception as e:
        logger.error(f"Error in toggle_digest: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def show_digest_time_selection(query, user_id: int) -> None:
    """
    Show time selection options for digest delivery.
    """
    try:
        time_text = get_text(user_id, 'digest.time_selection')
        
        # Get available times from translations
        times = get_text(user_id, 'digest.times')
        
        keyboard = []
        time_keys = ['00:00', '06:00', '08:00', '12:00', '16:00', '18:00', '20:00', '22:00']
        
        # Create rows of 2 buttons each
        for i in range(0, len(time_keys), 2):
            row = []
            for j in range(2):
                if i + j < len(time_keys):
                    time_key = time_keys[i + j]
                    time_label = times.get(time_key, f"{time_key} UTC")
                    row.append(InlineKeyboardButton(time_label, callback_data=f'digest_time_{time_key}'))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data='digest_menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(time_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_digest_time_selection: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def handle_set_digest_time(query, user_id: int, time_str: str) -> None:
    """
    Set the digest delivery time for the user.
    """
    try:
        set_digest_time(user_id, time_str)
        
        message = get_text(user_id, 'digest.time_updated', time=time_str)
        await query.edit_message_text(message, parse_mode='Markdown')
        
        # Show menu again after a brief delay
        await asyncio.sleep(2)
        await show_digest_menu(query, user_id)
        
    except Exception as e:
        logger.error(f"Error in set_digest_time: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def show_digest_preview(query, user_id: int) -> None:
    """
    Show a preview of what the digest content looks like.
    """
    try:
        from datetime import datetime
        current_date = datetime.now().strftime('%B %d, %Y')
        
        preview_content = get_text(user_id, 'digest.sample_content', date=current_date)
        
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data='digest_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(preview_content, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_digest_preview: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def show_digest_settings(query, user_id: int) -> None:
    """
    Show current digest settings.
    """
    try:
        user_settings = get_digest_settings(user_id)
        
        status = "Enabled" if user_settings['enabled'] else "Disabled"
        settings_text = get_text(user_id, 'digest.current_settings', 
                               status=status, 
                               time=user_settings['time'])
        
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data='digest_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_digest_settings: {e}")
        error_message = get_text(user_id, 'errors.general')
        await query.edit_message_text(error_message)

async def top_sales_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle top sales callback queries."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == 'top_sales_refresh':
        try:
            # Send loading message
            await query.edit_message_text(
                get_text(user_id, 'top_sales.loading')
            )
            
            # Fetch fresh data
            data = await fetch_top_sales_cached()
            
            if data:
                message = await format_top_sales_message(data, user_id)
                keyboard = get_top_sales_keyboard(user_id)
                
                await query.edit_message_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                log_user_action(user_id, "top_sales_refresh", "success")
            else:
                await query.edit_message_text(
                    get_text(user_id, 'top_sales.error')
                )
                
        except Exception as e:
            # For callback queries, we need to handle errors differently
            from error_handler import get_error_message
            error_message = get_error_message(user_id, e)
            await query.edit_message_text(error_message)
            logger.error(f"Error in top_sales_callback for user {user_id}: {type(e).__name__}: {e}", exc_info=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors that occur during bot operation.
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Try to send error message to user if update is available
    if isinstance(update, Update) and update.effective_message:
        try:
            user_id = update.effective_user.id if update.effective_user else None
            error_text = get_text(user_id, 'common.error') if user_id else "⚠️ An unexpected error occurred. Please try again later."
            await update.effective_message.reply_text(error_text)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def main() -> None:
    """
    Main function to initialize and run the bot.
    Supports both polling (local) and webhook (Heroku) modes.
    """
    try:
        # Initialize storage
        init_storage()
        init_search_storage()
        
        # Create the Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Initialize cache manager on startup
        async def post_init(app):
            await init_cache()
            logger.info("Cache manager initialized")
            # Start digest scheduler
            await start_digest_scheduler(app.bot)
            logger.info("Digest scheduler started")
        
        application.post_init = post_init
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("price", price_command))
        application.add_handler(CommandHandler("rankings", rankings_command))
        application.add_handler(CommandHandler("alerts", alerts_command))
        application.add_handler(CommandHandler("digest", digest_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("top_sales", top_sales_command))
        application.add_handler(CommandHandler("search", advanced_search_command))
        
        # Add callback query handlers
        application.add_handler(CallbackQueryHandler(rankings_callback, pattern='^rankings_'))
        application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
        application.add_handler(CallbackQueryHandler(digest_callback, pattern='^digest_'))
        application.add_handler(CallbackQueryHandler(top_sales_callback, pattern='^top_sales_'))
        application.add_handler(CallbackQueryHandler(quick_actions_callback, pattern='^quick_|^price_|^alert_|^back_to_|^main_|^menu_|^alerts_list$|^search_|^collections_page_|^help_|^collection_|^tutorial_|^popular_page_'))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Log bot startup
        logger.info("Bot is starting...")
        
        if HEROKU_APP_NAME:
            logger.info(f"Starting bot in hybrid mode (polling + web server) on port {PORT}")
            # Start a simple web server to satisfy Heroku's PORT requirement
            import threading
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            class HealthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Bot is running')
                
                def log_message(self, format, *args):
                    pass  # Suppress HTTP server logs
            
            # Start HTTP server in a separate thread
            server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            logger.info(f"Health check server started on port {PORT}")
            
            # Run bot in polling mode
            logger.info("Starting bot polling...")
            application.run_polling(drop_pending_updates=True)
        else:
            logger.info("Starting bot in polling mode (local development)")
            # Run the bot until the user presses Ctrl-C
            application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Error starting bot: {e}")
        raise
    finally:
        # Cleanup storage on shutdown
        try:
            cleanup_storage()
            # Skip async cleanup for now
            cleanup_search_storage()
        except Exception as e:
            logger.error(f"Error during storage cleanup: {e}")


if __name__ == '__main__':
    main()