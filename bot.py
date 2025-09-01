#!/usr/bin/env python3
"""
Telegram Bot Implementation

A simple Telegram bot created using python-telegram-bot library.
This bot includes basic commands and proper error handling.
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any
import ssl

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

# Configuration
BOT_TOKEN = "7556351017:AAHjwbA1vN_k6AJGQcM3jnR6-pXgBVperOk"

# NFT API Configuration
NFTPF_API_HOST = "nftpf-api-v0.p.rapidapi.com"
NFTPF_API_KEY = "7c50a84629msh50acacfc84ff5ebp1b3c3ajsn9fa81ab704f6"
OPENSEA_API_URL = "https://api.opensea.io/api/v1"


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.
    Sends a welcome message to the user.
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
        
        await update.message.reply_text(welcome_message)
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
        
        if not collections_data or 'projects' not in collections_data:
            logger.warning("No collections data received from API")
            return None
        
        projects = collections_data.get('projects', [])
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
        
        # Send "searching" message
        searching_text = get_text(user.id, 'price.searching', collection=collection_name)
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
        
        # 24h price change
        if price_change_24h_native:
            sign_native = "+" if price_change_24h_native >= 0 else ""
            sign_usd = "+" if price_change_24h_usd >= 0 else ""
            response_text += f"📈 **24h Change:** {sign_native}{price_change_24h_native:.1f}% {sign_usd}${price_change_24h_usd:.0f}\n"
        
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
        
        if not collections_data or 'projects' not in collections_data:
            error_text = get_text(user.id, 'rankings.error')
            await loading_msg.edit_text(error_text)
            return
        
        projects = collections_data.get('projects', [])
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
            # Send "loading" message
            loading_text = get_text(user.id, 'rankings.loading_next')
            await query.edit_message_text(loading_text)
            
            # Fetch next 10 collections
            collections_data = await fetch_nftpf_projects(offset=10, limit=10)
            
            if not collections_data or 'projects' not in collections_data:
                error_text = get_text(user.id, 'rankings.error')
                await query.edit_message_text(error_text)
                return
            
            projects = collections_data.get('projects', [])
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
                volume_24h = sales_temp_native.get('lowest', {}).get('val24h', 0)
                sales_24h = count_data.get('val24h', 0)
                sales_average = sales_temp_native.get('average', {}).get('val24h', 0)
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
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Log bot startup
        logger.info("Bot is starting...")
        
        # Run the bot until the user presses Ctrl-C
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Error starting bot: {e}")


if __name__ == '__main__':
    main()