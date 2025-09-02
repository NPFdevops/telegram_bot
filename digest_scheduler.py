#!/usr/bin/env python3
"""
Digest Scheduler Module

Handles scheduling and delivery of daily digest notifications to users.
Uses asyncio for background task management and timezone-aware scheduling.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Set
from telegram import Bot
from telegram.error import TelegramError

from user_storage import get_all_digest_users
from language_utils import get_text, get_user_language
from api_client import fetch_nftpf_projects

logger = logging.getLogger(__name__)

class DigestScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.task = None
        self.delivered_today: Set[str] = set()  # Track delivered digests for today
        
    async def start(self):
        """Start the digest scheduler."""
        if self.running:
            logger.warning("Digest scheduler is already running")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("Digest scheduler started")
        
    async def stop(self):
        """Stop the digest scheduler."""
        if not self.running:
            return
            
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Digest scheduler stopped")
        
    async def _scheduler_loop(self):
        """Main scheduler loop that runs every minute to check for digest deliveries."""
        while self.running:
            try:
                await self._check_and_deliver_digests()
                
                # Reset delivered_today at midnight UTC
                current_time = datetime.now(timezone.utc)
                if current_time.hour == 0 and current_time.minute == 0:
                    self.delivered_today.clear()
                    logger.info("Reset daily digest delivery tracking")
                    
            except Exception as e:
                logger.error(f"Error in digest scheduler loop: {e}")
                
            # Wait 60 seconds before next check
            await asyncio.sleep(60)
            
    async def _check_and_deliver_digests(self):
        """Check if any users need digest delivery at current time."""
        current_time = datetime.now(timezone.utc)
        current_hour_minute = f"{current_time.hour:02d}:{current_time.minute:02d}"
        
        # Only deliver on exact hour (minute 0)
        if current_time.minute != 0:
            return
            
        try:
            # Get all users with digest enabled
            digest_users = get_all_digest_users()
            
            for user_data in digest_users:
                user_id = user_data['user_id']
                user_time = user_data['time']
                delivery_key = f"{user_id}_{current_time.date()}"
                
                # Check if it's time to deliver and not already delivered today
                if user_time == current_hour_minute and delivery_key not in self.delivered_today:
                    await self._deliver_digest_to_user(user_id)
                    self.delivered_today.add(delivery_key)
                    
        except Exception as e:
            logger.error(f"Error checking digest deliveries: {e}")
            
    async def _deliver_digest_to_user(self, user_id: int):
        """Deliver daily digest to a specific user."""
        try:
            logger.info(f"Delivering daily digest to user {user_id}")
            
            # Generate digest content
            digest_content = await self._generate_digest_content(user_id)
            
            if digest_content:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=digest_content,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info(f"Daily digest delivered successfully to user {user_id}")
            else:
                logger.warning(f"Failed to generate digest content for user {user_id}")
                
        except TelegramError as e:
            if "bot was blocked by the user" in str(e).lower():
                logger.info(f"User {user_id} has blocked the bot, skipping digest delivery")
            else:
                logger.error(f"Telegram error delivering digest to user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error delivering digest to user {user_id}: {e}")
            
    async def _generate_digest_content(self, user_id: int) -> str:
        """Generate daily digest content for a user."""
        try:
            # Fetch top 10 collections for comprehensive digest
            rankings_data = await fetch_nftpf_projects(offset=0, limit=10)
            
            if not rankings_data:
                return None
                
            projects = rankings_data.get('data', rankings_data.get('projects', []))
            if not projects:
                return None
                
            # Build digest message
            current_date = datetime.now(timezone.utc).strftime('%B %d, %Y')
            user_lang = get_user_language(user_id)
            
            digest_text = f"📰 **{get_text(user_id, 'digest.daily_title')}**\n"
            digest_text += f"📅 {current_date}\n\n"
            
            # Top 5 collections by volume
            digest_text += f"🏆 **{get_text(user_id, 'digest.top_collections')}:**\n\n"
            
            total_volume = 0
            for i, project in enumerate(projects[:5], 1):
                name = project.get('name', 'Unknown')
                slug = project.get('slug', '')
                stats = project.get('stats', {})
                floor_info = stats.get('floorInfo', {})
                
                floor_price_eth = floor_info.get('currentFloorNative', 0)
                floor_change = floor_info.get('floorChange24h', 0)
                
                # Get 24h volume
                sales_temp_native = stats.get('salesTemporalityNative', {})
                volume_24h = sales_temp_native.get('1d', 0)
                total_volume += volume_24h
                
                # Format change indicator
                change_emoji = "📈" if floor_change > 0 else "📉" if floor_change < 0 else "➡️"
                change_text = f"({floor_change:+.1f}%)" if floor_change != 0 else "(0%)"
                
                digest_text += f"{i}. **{name}**\n"
                digest_text += f"   💰 Floor: {floor_price_eth:.3f} ETH {change_emoji} {change_text}\n"
                digest_text += f"   📊 24h Volume: {volume_24h:.1f} ETH\n\n"
            
            # Market summary
            digest_text += f"📊 **{get_text(user_id, 'digest.market_summary')}:**\n"
            digest_text += f"💎 Total Volume (Top 5): {total_volume:.1f} ETH\n"
            digest_text += f"📈 Collections Tracked: {len(projects)}\n\n"
            
            # Notable mentions (collections 6-10)
            if len(projects) > 5:
                digest_text += f"🔍 **{get_text(user_id, 'digest.notable_mentions')}:**\n"
                for project in projects[5:8]:  # Show 3 more
                    name = project.get('name', 'Unknown')
                    stats = project.get('stats', {})
                    floor_info = stats.get('floorInfo', {})
                    floor_price_eth = floor_info.get('currentFloorNative', 0)
                    
                    digest_text += f"• {name}: {floor_price_eth:.3f} ETH\n"
                digest_text += "\n"
            
            # Footer with actions
            digest_text += f"💡 *{get_text(user_id, 'digest.explore_more')}*\n\n"
            digest_text += f"⚙️ *{get_text(user_id, 'digest.manage_settings')}*"
            
            return digest_text
            
        except Exception as e:
            logger.error(f"Error generating digest content: {e}")
            return None
            
    async def deliver_preview_digest(self, user_id: int) -> str:
        """Generate and return a preview of the daily digest."""
        try:
            preview_content = await self._generate_digest_content(user_id)
            
            if preview_content:
                # Add preview header
                preview_text = f"👁️ **Daily Digest Preview**\n\n"
                preview_text += preview_content
                preview_text += f"\n\n📋 *This is how your daily digest will look*"
                return preview_text
            else:
                return get_text(user_id, 'digest.preview_error')
                
        except Exception as e:
            logger.error(f"Error generating digest preview: {e}")
            return get_text(user_id, 'errors.general')

# Global scheduler instance
_scheduler_instance = None

def get_scheduler() -> DigestScheduler:
    """Get the global scheduler instance."""
    return _scheduler_instance

def init_scheduler(bot: Bot) -> DigestScheduler:
    """Initialize the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DigestScheduler(bot)
    return _scheduler_instance

async def start_digest_scheduler(bot: Bot):
    """Start the digest scheduler."""
    scheduler = init_scheduler(bot)
    await scheduler.start()
    
async def stop_digest_scheduler():
    """Stop the digest scheduler."""
    if _scheduler_instance:
        await _scheduler_instance.stop()