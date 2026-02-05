"""BitAxe Discord Status Bot - Main entry point.

This bot monitors BitAxe/NerdAxe mining devices and posts status updates
to a Discord channel with automatic reconnection and error recovery.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from src.status_overview import format_status_embed
from src.config import (
    get_bot_token,
    get_channel_id,
    get_update_interval,
    get_project_root,
    get_devices,
    get_mention_user_id
)


def get_version() -> str:
    """Read version from VERSION file.
    
    Returns:
        Version string (e.g., '2.0.0') or 'unknown' if file not found
    """
    try:
        version_file = os.path.join(get_project_root(), 'VERSION')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return 'unknown'
    except Exception as e:
        logger.warning(f'Error reading VERSION file: {e}')
        return 'unknown'

# Logging configuration with rotation
log_dir = os.path.join(get_project_root(), "logs")
os.makedirs(log_dir, exist_ok=True)

log_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)

# File handler with rotation (5MB max, 3 backups)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, "bot.log"),
    maxBytes=5*1024*1024,
    backupCount=3
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Reduce discord.py logging noise
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)

# Bot setup with auto-reconnect
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global state
last_message: Optional[discord.Message] = None
last_update_time: Optional[datetime] = None
status_cache: Dict[str, Any] = {}
alert_cooldowns: Dict[str, datetime] = {}  # Track when alerts were last sent
ALERT_COOLDOWN = timedelta(minutes=15)  # Don't spam alerts

# Alert thresholds
TEMP_CRITICAL = 75  # °C
VR_TEMP_CRITICAL = 85  # °C
OFFLINE_ALERT_THRESHOLD = 3  # Alert after 3 failed checks


@bot.event
async def on_ready() -> None:
    """Handle bot ready event and start status update task.
    
    This event fires when the bot successfully connects to Discord.
    It starts the periodic status update loop.
    """
    version = get_version()
    logger.info(f'Bot connected as {bot.user} (ID: {bot.user.id})')
    logger.info(f'Version: {version}')
    logger.info(f'Monitoring {len(get_devices())} device(s)')
    logger.info(f'Target channel ID: {get_channel_id()}')
    logger.info(f'Update interval: {get_update_interval()}s')
    
    # Set bot presence with version
    try:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"BitAxe Devices | v{version}"
            )
        )
        logger.info(f'Bot presence set to: Watching BitAxe Devices | v{version}')
    except Exception as e:
        logger.error(f'Error setting bot presence: {e}')
    
    try:
        channel = bot.get_channel(get_channel_id())
        if channel:
            logger.info(f'Found target channel: {channel.name}')
        else:
            logger.error(f'Channel {get_channel_id()} not found!')
    except Exception as e:
        logger.error(f'Error accessing channel: {e}')
    
    if not update_status.is_running():
        update_status.start()
        logger.info('Status update task started')


@bot.event
async def on_disconnect() -> None:
    """Handle bot disconnect event.
    
    This event fires when the bot loses connection to Discord.
    The bot will automatically attempt to reconnect.
    """
    logger.warning('Bot disconnected from Discord')


@bot.event
async def on_resumed() -> None:
    """Handle bot resume event after reconnection.
    
    This event fires when the bot successfully reconnects to Discord
    after a connection loss.
    """
    logger.info('Bot reconnected to Discord')


async def check_and_send_alerts(channel: discord.TextChannel, device_name: str, status: Dict[str, Any]) -> None:
    """Check device status and send alerts for critical conditions.
    
    Args:
        channel: Discord channel to send alerts to
        device_name: Name of the device being checked
        status: Device status dictionary
    """
    global alert_cooldowns
    
    now = datetime.now()
    alerts = []
    
    # Check if device is offline
    if status.get('status') == 'Offline':
        offline_count = status.get('_offline_count', 0) + 1
        status['_offline_count'] = offline_count
        
        if offline_count >= OFFLINE_ALERT_THRESHOLD:
            alert_key = f"{device_name}_offline"
            if alert_key not in alert_cooldowns or (now - alert_cooldowns[alert_key]) > ALERT_COOLDOWN:
                alerts.append(f"⚠️ **{device_name}** ist offline! (seit {offline_count} Checks)")
                alert_cooldowns[alert_key] = now
    else:
        status['_offline_count'] = 0
    
    # Check temperature
    temp = status.get('temp')
    if temp and isinstance(temp, (int, float)) and temp >= TEMP_CRITICAL:
        alert_key = f"{device_name}_temp"
        if alert_key not in alert_cooldowns or (now - alert_cooldowns[alert_key]) > ALERT_COOLDOWN:
            alerts.append(f"🔥 **{device_name}** Kritische Temperatur: {temp}°C!")
            alert_cooldowns[alert_key] = now
    
    # Check VR temperature
    vr_temp = status.get('vrTemp')
    if vr_temp and isinstance(vr_temp, (int, float)) and vr_temp >= VR_TEMP_CRITICAL:
        alert_key = f"{device_name}_vrtemp"
        if alert_key not in alert_cooldowns or (now - alert_cooldowns[alert_key]) > ALERT_COOLDOWN:
            alerts.append(f"🔥 **{device_name}** Kritische VR-Temperatur: {vr_temp}°C!")
            alert_cooldowns[alert_key] = now
    
    # Send alerts if any
    if alerts:
        mention = f"<@{get_mention_user_id()}>" if get_mention_user_id() else ""
        alert_message = "\n".join(alerts)
        try:
            await channel.send(f"{mention}\n{alert_message}")
            logger.warning(f"Alert sent for {device_name}: {alert_message}")
        except discord.HTTPException as e:
            logger.error(f"Failed to send alert: {e}")


@tasks.loop(seconds=get_update_interval())
async def update_status() -> None:
    """Periodic task to update device status in Discord.
    
    This task runs every UPDATE_INTERVAL seconds and:
    - Fetches status from all configured devices
    - Caches results to reduce API calls
    - Checks for critical conditions and sends alerts
    - Updates or creates a Discord message with status embed
    - Implements rate limiting to avoid Discord API limits
    """
    global last_message, last_update_time, status_cache
    
    channel = bot.get_channel(get_channel_id())
    if not channel:
        logger.error(f"Channel {get_channel_id()} not accessible")
        return
    
    try:
        # Fetch device statuses (with caching in device_status module)
        embed, new_record_device, new_record_value = await format_status_embed()
        
        # Rate limiting: Wait if we updated too recently
        if last_update_time and (datetime.now() - last_update_time).total_seconds() < 1:
            await asyncio.sleep(1)
        
        # Update existing message or create new one
        if last_message:
            try:
                await last_message.edit(embed=embed)
                logger.debug('Status message updated successfully')
            except discord.NotFound:
                logger.warning('Previous message not found, creating new one')
                last_message = await channel.send(embed=embed)
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = e.retry_after if hasattr(e, 'retry_after') else 5
                    logger.warning(f'Rate limited, waiting {retry_after}s')
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f'HTTP error updating message: {e}')
                    raise
        else:
            last_message = await channel.send(embed=embed)
            logger.info('Initial status message created')
        
        last_update_time = datetime.now()
        
        # Check for alerts on all devices
        from src.device_status import get_all_device_statuses
        all_statuses = await get_all_device_statuses()
        for device_name, status in all_statuses.items():
            await check_and_send_alerts(channel, device_name, status)
        
        # Send notification for new records
        if new_record_device and new_record_value:
            mention = f"<@{get_mention_user_id()}>" if get_mention_user_id() else ""
            try:
                await channel.send(
                    f"{mention} 🎉 Neuer Best-Difficulty Rekord für **{new_record_device}**: {new_record_value}"
                )
                logger.info(f'New record notification sent for {new_record_device}')
            except discord.HTTPException as e:
                logger.error(f'Failed to send record notification: {e}')
    
    except discord.Forbidden:
        logger.error('Bot lacks permissions to send/edit messages in channel')
    except discord.HTTPException as e:
        logger.error(f'Discord HTTP error in update_status: {e}')
    except Exception as e:
        logger.error(f'Unexpected error in update_status: {e}', exc_info=True)


@update_status.before_loop
async def before_update_status() -> None:
    """Wait for bot to be ready before starting update loop.
    
    This ensures the bot is fully connected before attempting
    to send messages.
    """
    logger.info('Waiting for bot to be ready before starting updates...')
    await bot.wait_until_ready()
    logger.info('Bot ready, starting status updates')


@update_status.error
async def update_status_error(error: Exception) -> None:
    """Handle errors in the update status task.
    
    Args:
        error: The exception that occurred
    """
    logger.error(f'Error in update_status task: {error}', exc_info=True)
    # Task will automatically restart after error


if __name__ == "__main__":
    """Main entry point with error recovery."""
    token = get_bot_token()
    
    if not token:
        logger.error('No bot token configured! Set DISCORD_BOT_TOKEN or configure config.ini')
        sys.exit(1)
    
    if not get_channel_id():
        logger.error('No channel ID configured! Set DISCORD_CHANNEL_ID or configure config.ini')
        sys.exit(1)
    
    try:
        logger.info('Starting BitAxe Discord Status Bot...')
        # Run with auto-reconnect enabled (default)
        bot.run(token, reconnect=True)
    except discord.LoginFailure:
        logger.error('Invalid bot token provided')
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info('Bot stopped by user')
    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)
    finally:
        logger.info('Bot shutdown complete')
