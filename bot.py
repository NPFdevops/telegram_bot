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
        welcome_message = (
            f"🤖 Hello {user.first_name}!\n\n"
            "Welcome to this Telegram bot! I'm here to help you.\n\n"
            "Use /help to see available commands."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"User {user.id} ({user.username}) started the bot")
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )


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
        # Check if collection name is provided
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a collection name.\n\n"
                "Usage: `/price <collection_name>`\n\n"
                "Example: `/price cryptopunks`",
                parse_mode='Markdown'
            )
            return
        
        collection_name = " ".join(context.args)
        
        # Send "searching" message
        searching_msg = await update.message.reply_text(
            f"🔍 Searching for **{collection_name}**...",
            parse_mode='Markdown'
        )
        
        # Search for collection data
        collection_data = await search_nftpf_collection(collection_name)
        
        if not collection_data:
            await searching_msg.edit_text(
                f"❌ Collection **{collection_name}** not found.\n"
                "Please check the spelling and try again.",
                parse_mode='Markdown'
            )
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
            await update.message.reply_text(
                "❌ Sorry, something went wrong while fetching NFT data. Please try again later."
            )
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
            help_text = (
                "🔔 **NFT Price Alerts**\n\n"
                "**Commands:**\n"
                "`/alerts list` - View your active alerts\n"
                "`/alerts add <collection> <price>` - Add price alert\n"
                "`/alerts remove <id>` - Remove alert by ID\n\n"
                "**Examples:**\n"
                "`/alerts add cryptopunks 50` - Alert when CryptoPunks floor hits 50 ETH\n"
                "`/alerts add bored-ape-yacht-club 30` - Alert for BAYC at 30 ETH\n\n"
                "💡 *Alerts check prices every hour*"
            )
            await update.message.reply_text(help_text, parse_mode='Markdown')
            return
        
        command = context.args[0].lower()
        
        if command == "list":
            # For now, show a placeholder message
            response_text = (
                "📋 **Your Active Alerts**\n\n"
                "🔄 No active alerts found.\n\n"
                "Use `/alerts add <collection> <price>` to create your first alert!"
            )
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        elif command == "add":
            if len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Please provide collection name and target price.\n\n"
                    "Usage: `/alerts add <collection> <price>`\n"
                    "Example: `/alerts add cryptopunks 50`",
                    parse_mode='Markdown'
                )
                return
            
            collection_name = context.args[1]
            try:
                target_price = float(context.args[2])
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid price format. Please enter a valid number.\n\n"
                    "Example: `/alerts add cryptopunks 50`",
                    parse_mode='Markdown'
                )
                return
            
            # For now, show a success message (in a real implementation, this would save to database)
            response_text = (
                f"✅ **Alert Created!**\n\n"
                f"📊 Collection: {collection_name}\n"
                f"💰 Target Price: {target_price} ETH\n\n"
                f"🔔 You'll be notified when the floor price reaches your target.\n\n"
                f"*Note: This is a demo implementation. Full alert functionality coming soon!*"
            )
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        elif command == "remove":
            if len(context.args) < 2:
                await update.message.reply_text(
                    "❌ Please provide alert ID to remove.\n\n"
                    "Usage: `/alerts remove <id>`\n"
                    "Use `/alerts list` to see your alert IDs.",
                    parse_mode='Markdown'
                )
                return
            
            alert_id = context.args[1]
            # For now, show a placeholder message
            response_text = (
                f"✅ **Alert Removed**\n\n"
                f"🗑️ Alert ID {alert_id} has been removed.\n\n"
                f"*Note: This is a demo implementation. Full alert functionality coming soon!*"
            )
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        else:
            await update.message.reply_text(
                "❌ Unknown alerts command.\n\n"
                "Use `/alerts` to see available options.",
                parse_mode='Markdown'
            )
        
        logger.info(f"Alerts command used by user {user_id}: {' '.join(context.args)}")
        
    except Exception as e:
        logger.error(f"Error in alerts_command: {e}")
        try:
            await update.message.reply_text(
                "❌ Sorry, something went wrong with alerts. Please try again later."
            )
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
        # Send "loading" message
        loading_msg = await update.message.reply_text(
            "📊 Loading top NFT collections by market cap..."
        )
        
        # Fetch NFT collections data from NFTPriceFloor API
        collections_data = await fetch_nftpf_projects(offset=0, limit=10)
        
        if not collections_data or 'projects' not in collections_data:
            await loading_msg.edit_text(
                "❌ Unable to fetch rankings data. Please try again later."
            )
            return
        
        projects = collections_data.get('projects', [])
        if not projects:
            await loading_msg.edit_text(
                "❌ No rankings data available. Please try again later."
            )
            return
        
        # Format the rankings response
        response_text = "🏆 **Top NFT Collections**\n\n"
        
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
        keyboard = [[
            InlineKeyboardButton("➡️ Next 10 Collections", callback_data="rankings_next_10")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response_text += "\n🔄 *Data from NFTPriceFloor API*"
        
        await loading_msg.edit_text(
            response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Rankings command used by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in rankings_command: {e}")
        try:
            await update.message.reply_text(
                "❌ Sorry, something went wrong while fetching rankings data. Please try again later."
            )
        except:
            pass


async def rankings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries for rankings pagination.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "rankings_next_10":
            # Send "loading" message
            await query.edit_message_text(
                "📊 Loading next 10 NFT collections..."
            )
            
            # Fetch next 10 collections
            collections_data = await fetch_nftpf_projects(offset=10, limit=10)
            
            if not collections_data or 'projects' not in collections_data:
                await query.edit_message_text(
                    "❌ Unable to fetch more rankings data. Please try again later."
                )
                return
            
            projects = collections_data.get('projects', [])
            if not projects:
                await query.edit_message_text(
                    "❌ No more collections available."
                )
                return
            
            # Format the response for next 10
            response_text = "🏆 **Top NFT Collections - Next 10**\n\n"
            
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
            keyboard = [[
                InlineKeyboardButton("⬅️ Back to Top 10", callback_data="rankings_back_10")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            response_text += "\n🔄 *Data from NFTPriceFloor API*"
            
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
            await query.edit_message_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
        except:
            pass


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command.
    Provides usage instructions and available commands.
    """
    try:
        help_text = (
            "📋 **Available Commands:**\n\n"
            "/start - Welcome message and bot introduction\n"
            "/help - Show this help message\n"
            "/price <collection> - Get NFT collection floor price\n"
            "/rankings - View top NFT collections by volume\n"
            "/alerts - Manage price alerts\n"
            "\n"
            "🔧 **How to use:**\n"
            "Simply type any of the commands above to interact with the bot.\n\n"
            "If you encounter any issues, please try again or contact support."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
        logger.info(f"Help command used by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong while loading help. Please try again."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors that occur during bot operation.
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Try to send error message to user if update is available
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again later."
            )
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
        # application.add_handler(CommandHandler("top_sales", top_sales_command))  # Temporarily deactivated
        
        # Add callback query handler
        application.add_handler(CallbackQueryHandler(rankings_callback))
        
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