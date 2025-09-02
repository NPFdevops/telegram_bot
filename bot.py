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
WEBHOOK_URL = f'https://{HEROKU_APP_NAME}.herokuapp.com' if HEROKU_APP_NAME else None


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.
    Sends a welcome message with interactive quick actions.
    """
    try:
        user = update.effective_user
        
        # Detect and set user language if not already set
        current_lang = get_user_language(user.id)
        if current_lang == 'en':  # Default language, try to detect
            detected_lang = detect_user_language_from_telegram(user)
            set_user_language(user.id, detected_lang)
        
        # Get welcome message in user's language
        welcome_message = get_text(user.id, 'welcome.greeting', name=user.first_name)
        
        # Create quick action buttons
        keyboard = [
            [
                InlineKeyboardButton(get_text(user.id, 'welcome.quick_actions.popular_collections'), callback_data='quick_popular'),
                InlineKeyboardButton(get_text(user.id, 'welcome.quick_actions.top_rankings'), callback_data='quick_rankings')
            ],
            [
                InlineKeyboardButton(get_text(user.id, 'welcome.quick_actions.set_alert'), callback_data='quick_alert'),
                InlineKeyboardButton(get_text(user.id, 'welcome.quick_actions.tutorial'), callback_data='quick_tutorial')
            ],
            [
                InlineKeyboardButton(get_text(user.id, 'welcome.quick_actions.help'), callback_data='quick_help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
        logger.info(f"User {user.id} ({user.username}) started the bot")
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        error_message = get_text(user.id, 'errors.general') if 'user' in locals() else "Sorry, something went wrong. Please try again later."
        await update.message.reply_text(error_message)


# NFT API Helper Functions
async def fetch_nftpf_project_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific NFT project by slug from NFTPriceFloor API.
    """
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects/{slug}"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.warning(f"NFTPriceFloor API request failed with status {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching NFTPriceFloor project: {e}")
        return None


async def search_nftpf_collection(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    Search for a specific NFT collection by name from NFTPriceFloor API.
    """
    try:
        # First get all projects and search for the collection
        collections_data = await fetch_nftpf_projects(offset=0, limit=200)
        
        if not collections_data:
            logger.warning("No collections data received from API")
            return None
        
        # Handle both 'data' and 'projects' keys for API response compatibility
        projects = collections_data.get('data', collections_data.get('projects', []))
        logger.info(f"Searching through {len(projects)} projects for '{collection_name}'")
        
        # Search for collection by name (case-insensitive)
        collection_name_lower = collection_name.lower().strip()
        
        # Try exact match first
        for project in projects:
            project_name = project.get('name', '').lower().strip()
            if project_name == collection_name_lower:
                logger.info(f"Found exact match: {project.get('name')}")
                slug = project.get('slug')
                if slug:
                    detailed_data = await fetch_nftpf_project_by_slug(slug)
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
                    detailed_data = await fetch_nftpf_project_by_slug(slug)
                    if detailed_data:
                        return detailed_data
                return project
        
        logger.warning(f"No match found for '{collection_name}'")
        return None
                    
    except Exception as e:
        logger.error(f"Error searching NFT collection: {e}")
        return None


# NFT Command Handlers
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /price command.
    Get NFT collection floor price and basic information.
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
        
        # Search for collection data
        collection_data = await search_nftpf_collection(collection_name)
        
        if not collection_data:
            not_found_text = get_text(user.id, 'price.not_found', collection=collection_name)
            await searching_msg.edit_text(not_found_text, parse_mode='Markdown')
            return
        
        # Extract relevant information from the new API structure
        stats = collection_data.get('stats', {})
        details = collection_data.get('details', {})
        
        name = details.get('name', 'Unknown')
        slug = details.get('slug', '')
        ranking = details.get('ranking', 0)
        
        # Floor price information
        floor_info = stats.get('floorInfo', {})
        floor_price_eth = floor_info.get('currentFloorNative', 0)
        floor_price_usd = floor_info.get('currentFloorUsd', 0)
        
        # Supply and other stats
        total_supply = stats.get('totalSupply', 0)
        listed_count = stats.get('listedCount', 0)
        total_owners = stats.get('totalOwners', 0)
        
        # 24h price changes
        floor_temp_native = stats.get('floorTemporalityNative', {})
        floor_temp_usd = stats.get('floorTemporalityUsd', {})
        price_change_24h_native = floor_temp_native.get('diff24h', 0)
        price_change_24h_usd = floor_temp_usd.get('diff24h', 0)
        
        # 24h volume and sales
        sales_temp_native = stats.get('salesTemporalityNative', {})
        volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
        sales_24h = sales_temp_native.get('count', {}).get('val24h', 0)
        
        # Create hyperlink for collection name
        collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)" if slug else name
        
        # Format the response
        response_text = f"📊 **{collection_link}**\n"
        if ranking:
            response_text += f"🏆 **Rank:** #{ranking}\n"
        response_text += "\n"
        
        # Floor price in ETH and USD
        if floor_price_eth:
            floor_eth = f"{floor_price_eth:.3f} ETH"
            floor_usd = f"${floor_price_usd:,.0f}" if floor_price_usd else "N/A"
            response_text += f"🏠 **Floor Price:** {floor_eth} ({floor_usd})\n"
        
        # 24h price change with dynamic visual indicators
        if price_change_24h_native:
            sign_native = "+" if price_change_24h_native >= 0 else ""
            sign_usd = "+" if price_change_24h_usd >= 0 else ""
            
            # Dynamic emoji based on change percentage
            if price_change_24h_native > 15:
                change_emoji = "🚀"  # Strong positive
            elif price_change_24h_native > 5:
                change_emoji = "📈"  # Positive
            elif price_change_24h_native > 0:
                change_emoji = "📊"  # Slight positive
            elif price_change_24h_native > -5:
                change_emoji = "📉"  # Slight negative
            elif price_change_24h_native > -15:
                change_emoji = "⬇️"  # Negative
            else:
                change_emoji = "💥"  # Strong negative
                
            response_text += f"{change_emoji} **24h Change:** {sign_native}{price_change_24h_native:.1f}% {sign_usd}${price_change_24h_usd:.0f}\n"
        
        # 24h volume and sales
        if volume_24h:
            if volume_24h >= 1000:
                volume_str = f"{volume_24h/1000:.1f}K ETH"
            else:
                volume_str = f"{volume_24h:.2f} ETH"
            response_text += f"💰 **24h Volume:** {volume_str} ({sales_24h} sales)\n"
        
        # Supply and ownership info
        if total_supply:
            response_text += f"📦 **Total Supply:** {total_supply:,}\n"
        if listed_count:
            response_text += f"🏪 **Listed:** {listed_count:,}\n"
        if total_owners:
            response_text += f"👥 **Owners:** {total_owners:,}\n"
        
        response_text += "\n🔄 *Data from NFTPriceFloor API*"
        
        await searching_msg.edit_text(response_text, parse_mode='Markdown')
        logger.info(f"Price command used for collection '{collection_name}' by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in price_command: {e}")
        try:
            user = update.effective_user
            error_message = get_text(user.id, 'price.error')
            await update.message.reply_text(error_message)
        except:
            pass


# fetch_top_sales function temporarily deactivated
# async def fetch_top_sales() -> Optional[Dict[str, Any]]:
#     """
#     Fetch top NFT collections data from NFTPriceFloor API and simulate top sales.
#     Since the top-sales endpoint is not available, we'll use the projects-v2 endpoint
#     and show the top collections by volume.
#     """
#     return None


# /top_sales command temporarily deactivated
# async def top_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """
#     Handle the /top_sales command.
#     Show top NFT collections by 24h volume.
#     """
#     await update.message.reply_text(
#         "🚧 The /top_sales command is temporarily unavailable. Please try again later."
#     )


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /alerts command.
    Manage price alerts for NFT collections.
    """
    try:
        user_id = update.effective_user.id
        
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
        
        logger.info(f"Alerts command used by user {user_id}: {' '.join(context.args)}")
        
    except Exception as e:
        logger.error(f"Error in alerts_command: {e}")
        try:
            error_text = get_text(user_id, 'alerts.error')
            await update.message.reply_text(error_text)
        except:
            pass


async def fetch_nftpf_projects(offset: int = 0, limit: int = 10) -> Optional[Dict[str, Any]]:
    """
    Fetch NFT projects data from NFTPriceFloor API.
    """
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects-v2"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            params = {
                'offset': offset,
                'limit': limit
            }
            
            logger.info(f"Making request to {url} with params {params}")
            async with session.get(url, headers=headers, params=params) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Response data keys: {list(data.keys()) if data else 'None'}")
                    logger.info(f"Data type: {type(data)}")
                    if isinstance(data, dict) and 'data' in data:
                        logger.info(f"Number of projects in data: {len(data['data'])}")
                    return data
                else:
                    response_text = await response.text()
                    logger.warning(f"NFTPriceFloor API request failed with status {response.status}, response: {response_text}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching NFTPriceFloor data: {e}")
        return None


async def rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /rankings command.
    Show top NFT collections by market cap.
    """
    try:
        user = update.effective_user
        
        # Send "loading" message
        loading_text = get_text(user.id, 'rankings.loading')
        loading_msg = await update.message.reply_text(loading_text)
        
        # Fetch NFT collections data from NFTPriceFloor API
        collections_data = await fetch_nftpf_projects(offset=0, limit=10)
        
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
            volume_24h = sales_temp_native.get('lowest', {}).get('val24h', 0)
            sales_24h = count_data.get('val24h', 0)
            sales_average = sales_temp_native.get('average', {}).get('val24h', 0)
            sales_count = sales_temp_native.get('count', {}).get('val24h', 0)
            
            # Create hyperlink for collection name
            collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
            
            # Format floor price in ETH and USD
            floor_eth = f"{floor_price_eth:.1f} ETH" if floor_price_eth else "N/A"
            floor_usd = f"${floor_price_usd:,.0f}" if floor_price_usd else "N/A"
            floor_display = f"{floor_eth} ({floor_usd})" if floor_price_eth and floor_price_usd else "N/A"
            
            # Format 24h price change
            if price_change_24h:
                sign = "+" if price_change_24h >= 0 else ""
                price_change_display = f"{sign}{price_change_24h:.1f}% {sign}${price_change_24h_usd:.1f}"
            else:
                price_change_display = "N/A"
            
            # Format 24h volume and sales
            vol_24h = f"{volume_24h:.1f} ETH" if volume_24h else "N/A"
            sales_count = f"{int(sales_24h)} sales" if sales_24h else "N/A"
            volume_sales_display = f"{vol_24h} ({sales_count})" if volume_24h and sales_24h else "N/A"
            
            response_text += (
                f"{i}. {collection_link}\n"
                f"   📈 24h Change: {price_change_display}\n"
                f"   🏠 Floor: {floor_display}\n"
                f"   📊 24h Volume: {volume_sales_display}\n\n"
            )
        
        # Add pagination button
        next_button_text = get_text(user.id, 'rankings.next_button')
        keyboard = [[
            InlineKeyboardButton(next_button_text, callback_data="rankings_next_10")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        footer_text = get_text(user.id, 'rankings.footer')
        response_text += f"\n{footer_text}"
        
        await loading_msg.edit_text(
            response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Rankings command used by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in rankings_command: {e}")
        try:
            error_text = get_text(user.id, 'rankings.error')
            await update.message.reply_text(error_text)
        except:
            pass


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
            collections_data = await fetch_nftpf_projects(offset=10, limit=10)
            
            if not collections_data:
                error_text = get_text(user.id, 'rankings.error')
                await query.edit_message_text(error_text)
                return
            
            # Handle both 'data' and 'projects' keys for API response compatibility
            projects = collections_data.get('data', collections_data.get('projects', []))
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
                
                # Create hyperlink for collection name
                collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
                
                # Format floor price in ETH and USD
                floor_eth = f"{floor_price_eth:.1f} ETH" if floor_price_eth else "N/A"
                floor_usd = f"${floor_price_usd:,.0f}" if floor_price_usd else "N/A"
                floor_display = f"{floor_eth} ({floor_usd})" if floor_price_eth and floor_price_usd else "N/A"
                
                # Format 24h price change
                if price_change_24h:
                    sign = "+" if price_change_24h >= 0 else ""
                    price_change_display = f"{sign}{price_change_24h:.1f}% {sign}${price_change_24h_usd:.1f}"
                else:
                    price_change_display = "N/A"
                
                # Format 24h volume and sales
                vol_24h = f"{volume_24h:.1f} ETH" if volume_24h else "N/A"
                sales_count = f"{int(sales_24h)} sales" if sales_24h else "N/A"
                volume_sales_display = f"{vol_24h} ({sales_count})" if volume_24h and sales_24h else "N/A"
                
                response_text += (
                    f"{i}. {collection_link}\n"
                    f"   📈 24h Change: {price_change_display}\n"
                    f"   🏠 Floor: {floor_display}\n"
                    f"   📊 24h Volume: {volume_sales_display}\n\n"
                )
            
            # Add back button
            back_button_text = get_text(user.id, 'rankings.back_button')
            keyboard = [[
                InlineKeyboardButton(back_button_text, callback_data="rankings_back_10")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            footer_text = get_text(user.id, 'rankings.footer')
            response_text += f"\n{footer_text}"
            
            await query.edit_message_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        elif query.data == "rankings_back_10":
            # Go back to top 10
            await rankings_command(update, context)
            
    except Exception as e:
        logger.error(f"Error in rankings_callback: {e}")
        try:
            error_text = get_text(user.id, 'rankings.error')
            await query.edit_message_text(error_text)
        except:
            pass


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
                
                # Send confirmation in the new language
                confirmation_text = get_text(user.id, 'language.changed')
                await query.edit_message_text(confirmation_text)
                
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
        
        if callback_data == 'quick_popular':
            await show_popular_collections(query, user.id)
        elif callback_data == 'quick_rankings':
            # Redirect to rankings command
            await rankings_command_from_callback(query, user.id)
        elif callback_data == 'quick_alert':
            await show_alert_setup(query, user.id)
        elif callback_data == 'quick_tutorial':
            await show_tutorial(query, user.id)
        elif callback_data == 'quick_help':
            await show_help_menu(query, user.id)
        elif callback_data == 'search_collections':
            await show_collection_search(query, user.id)
        elif callback_data == 'quick_access':
            await show_quick_access_collections(query, user.id)
        elif callback_data.startswith('collection_'):
            collection_slug = callback_data.replace('collection_', '')
            await show_collection_actions(query, user.id, collection_slug)
        elif callback_data.startswith('price_'):
            collection_slug = callback_data.replace('price_', '')
            await get_collection_price_from_callback(query, user.id, collection_slug)
        elif callback_data.startswith('alert_'):
            collection_slug = callback_data.replace('alert_', '')
            await setup_alert_from_callback(query, user.id, collection_slug)
        elif callback_data.startswith('popular_page_'):
            page = int(callback_data.replace('popular_page_', ''))
            await show_popular_collections(query, user.id, page)
        elif callback_data == 'back_to_popular':
            await show_popular_collections(query, user.id)
        elif callback_data == 'main_menu':
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
            elif menu_type == 'settings':
                await language_command_from_callback(query, user.id)
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


async def show_collection_search(query, user_id: int) -> None:
    """
    Show collection search interface with input instructions.
    """
    try:
        search_text = get_text(user_id, 'search.instructions')
        back_button_text = get_text(user_id, 'navigation.back')
        
        keyboard = [
            [InlineKeyboardButton(back_button_text, callback_data='main_menu')]
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
            
            # Add action buttons for each collection
            view_price_text = get_text(user_id, 'popular_collections.view_price')
            set_alert_text = get_text(user_id, 'popular_collections.set_alert')
            
            keyboard.append([
                InlineKeyboardButton(f"{view_price_text} {name[:15]}...", callback_data=f'price_{slug}'),
                InlineKeyboardButton(set_alert_text, callback_data=f'alert_{slug}')
            ])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'collections_page_{page-1}'))
        if end_idx < len(curated_collections):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f'collections_page_{page+1}'))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Add search and quick access buttons
        keyboard.append([
            InlineKeyboardButton("🔍 Search Collections", callback_data='search_collections'),
            InlineKeyboardButton("⚡ Quick Access", callback_data='quick_access')
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
    Display the main menu with categorized options.
    """
    try:
        menu_text = get_text(user_id, 'menus.main.title')
        
        keyboard = [
            [
                InlineKeyboardButton(get_text(user_id, 'menus.main.market_data'), callback_data='menu_market'),
                InlineKeyboardButton(get_text(user_id, 'menus.main.collections'), callback_data='menu_collections')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'menus.main.alerts'), callback_data='menu_alerts'),
                InlineKeyboardButton(get_text(user_id, 'menus.main.settings'), callback_data='menu_settings')
            ],
            [
                InlineKeyboardButton(get_text(user_id, 'menus.main.help'), callback_data='quick_help')
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}")
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
        keyboard = get_language_options_keyboard()
        
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
        rankings_data = await fetch_nftpf_projects(offset=0, limit=10)
        
        if not rankings_data:
            error_message = get_text(user_id, 'rankings.error')
            await query.edit_message_text(error_message)
            return
        
        # Handle both 'data' and 'projects' keys for API response compatibility
        projects = rankings_data.get('data', rankings_data.get('projects', []))
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
            
            # Get 24h volume from salesTemporalityNative
            sales_temp_native = stats.get('salesTemporalityNative', {})
            volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
            
            # Create hyperlink for collection name
            collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)"
            
            rankings_text += get_text(user_id, 'rankings.item',
                                    rank=i, name=collection_link, 
                                    floor=f"{floor_price_eth:.2f}" if floor_price_eth else "N/A",
                                    volume=f"{volume_24h:.2f}" if volume_24h else "N/A")
        
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


async def get_collection_price_from_callback(query, user_id: int, collection_slug: str) -> None:
    """
    Get collection price from callback button.
    This function displays identical information to the /price command.
    """
    try:
        searching_message = get_text(user_id, 'price.searching', collection=collection_slug)
        await query.edit_message_text(searching_message)
        
        # Search for collection data using the same method as /price command
        collection_data = await search_nftpf_collection(collection_slug)
        
        if not collection_data:
            not_found_message = get_text(user_id, 'price.not_found', collection=collection_slug)
            keyboard = [[InlineKeyboardButton(get_text(user_id, 'common.back'), callback_data='back_to_popular')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(not_found_message, reply_markup=reply_markup)
            return
        
        # Extract relevant information from the new API structure (same as /price command)
        stats = collection_data.get('stats', {})
        details = collection_data.get('details', {})
        
        name = details.get('name', 'Unknown')
        slug = details.get('slug', '')
        ranking = details.get('ranking', 0)
        
        # Floor price information
        floor_info = stats.get('floorInfo', {})
        floor_price_eth = floor_info.get('currentFloorNative', 0)
        floor_price_usd = floor_info.get('currentFloorUsd', 0)
        
        # Supply and other stats
        total_supply = stats.get('totalSupply', 0)
        listed_count = stats.get('listedCount', 0)
        total_owners = stats.get('totalOwners', 0)
        
        # 24h price changes
        floor_temp_native = stats.get('floorTemporalityNative', {})
        floor_temp_usd = stats.get('floorTemporalityUsd', {})
        price_change_24h_native = floor_temp_native.get('diff24h', 0)
        price_change_24h_usd = floor_temp_usd.get('diff24h', 0)
        
        # 24h volume and sales
        sales_temp_native = stats.get('salesTemporalityNative', {})
        volume_24h = sales_temp_native.get('volume', {}).get('val24h', 0)
        sales_24h = sales_temp_native.get('count', {}).get('val24h', 0)
        
        # Create hyperlink for collection name
        collection_link = f"[{name}](https://nftpricefloor.com/{slug}?=tbot)" if slug else name
        
        # Format the response (identical to /price command)
        response_text = f"📊 **{collection_link}**\n"
        if ranking:
            response_text += f"🏆 **Rank:** #{ranking}\n"
        response_text += "\n"
        
        # Floor price in ETH and USD
        if floor_price_eth:
            floor_eth = f"{floor_price_eth:.3f} ETH"
            floor_usd = f"${floor_price_usd:,.0f}" if floor_price_usd else "N/A"
            response_text += f"🏠 **Floor Price:** {floor_eth} ({floor_usd})\n"
        
        # 24h price change with dynamic visual indicators
        if price_change_24h_native:
            sign_native = "+" if price_change_24h_native >= 0 else ""
            sign_usd = "+" if price_change_24h_usd >= 0 else ""
            
            # Dynamic emoji based on change percentage
            if price_change_24h_native > 15:
                change_emoji = "🚀"  # Strong positive
            elif price_change_24h_native > 5:
                change_emoji = "📈"  # Positive
            elif price_change_24h_native > 0:
                change_emoji = "📊"  # Slight positive
            elif price_change_24h_native > -5:
                change_emoji = "📉"  # Slight negative
            elif price_change_24h_native > -15:
                change_emoji = "⬇️"  # Negative
            else:
                change_emoji = "💥"  # Strong negative
                
            response_text += f"{change_emoji} **24h Change:** {sign_native}{price_change_24h_native:.1f}% {sign_usd}${price_change_24h_usd:.0f}\n"
        
        # 24h volume and sales
        if volume_24h:
            if volume_24h >= 1000:
                volume_str = f"{volume_24h/1000:.1f}K ETH"
            else:
                volume_str = f"{volume_24h:.2f} ETH"
            response_text += f"💰 **24h Volume:** {volume_str} ({sales_24h} sales)\n"
        
        # Supply and ownership info
        if total_supply:
            response_text += f"📦 **Total Supply:** {total_supply:,}\n"
        if listed_count:
            response_text += f"🏪 **Listed:** {listed_count:,}\n"
        if total_owners:
            response_text += f"👥 **Owners:** {total_owners:,}\n"
        
        response_text += "\n🔄 *Data from NFTPriceFloor API*"
        
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
        collection_name = get_text(user_id, f'popular_collections.{collection_slug}.name')
        collection_desc = get_text(user_id, f'popular_collections.{collection_slug}.description')
        collection_tags = get_text(user_id, f'popular_collections.{collection_slug}.tags')
        
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
        # Create the Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("price", price_command))
        application.add_handler(CommandHandler("rankings", rankings_command))
        application.add_handler(CommandHandler("alerts", alerts_command))
        application.add_handler(CommandHandler("language", language_command))
        # application.add_handler(CommandHandler("top_sales", top_sales_command))  # Temporarily deactivated
        
        # Add callback query handlers
        application.add_handler(CallbackQueryHandler(rankings_callback, pattern='^rankings_'))
        application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
        application.add_handler(CallbackQueryHandler(quick_actions_callback, pattern='^quick_|^price_|^alert_|^back_to_|^main_menu$|^menu_|^alerts_list$|^search_collections$|^collections_page_|^help_|^collection_'))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Log bot startup
        logger.info("Bot is starting...")
        
        # Check if running on Heroku (webhook mode) or locally (polling mode)
        if WEBHOOK_URL and HEROKU_APP_NAME:
            logger.info(f"Starting bot in webhook mode on port {PORT}")
            logger.info(f"Webhook URL: {WEBHOOK_URL}")
            
            # Start webhook
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path="/webhook",
                webhook_url=f"{WEBHOOK_URL}webhook",
                drop_pending_updates=True
            )
        else:
            logger.info("Starting bot in polling mode (local development)")
            # Run the bot until the user presses Ctrl-C
            application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Error starting bot: {e}")
        raise


if __name__ == '__main__':
    main()