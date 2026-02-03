"""Configuration management with environment variable support."""

import os
from configparser import ConfigParser
from typing import Optional, List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Global default thresholds
DEFAULT_TEMP_THRESHOLDS = "60,65,70"
DEFAULT_FAN_THRESHOLDS = "0,2000,3500,7500"
DEFAULT_VOLT_THRESHOLDS = "0.95,1.1,1.3"
DEFAULT_VR_TEMP_THRESHOLDS = "65,75,80"
DEFAULT_UPDATE_INTERVAL = 30


class Config:
    """Configuration loader with environment variable fallback.
    
    Supports loading configuration from both config.ini files and environment variables.
    Environment variables take precedence over config file values.
    
    Examples:
        >>> config = Config()
        >>> token = config.get("Bot", "token", env_var="DISCORD_BOT_TOKEN")
        >>> devices = config.get_devices()
    """
    
    def __init__(self) -> None:
        """Initialize configuration loader."""
        self.config = ConfigParser()
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(self.project_root, "config.ini")
        
        # Load config file if exists
        if os.path.exists(config_path):
            try:
                self.config.read(config_path)
                logger.info(f"Configuration loaded from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        else:
            logger.warning(f"No config.ini found at {config_path}, using environment variables only")
    
    def get(self, section: str, key: str, fallback: Any = None, env_var: Optional[str] = None) -> Any:
        """Get config value with environment variable fallback.
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value if not found
            env_var: Environment variable name to check first
            
        Returns:
            Configuration value or fallback
        """
        # Check environment variable first
        if env_var and os.getenv(env_var):
            return os.getenv(env_var)
        
        # Fall back to config file
        try:
            return self.config.get(section, key)
        except:
            return fallback
    
    def getint(self, section: str, key: str, fallback: int = 0, env_var: Optional[str] = None) -> int:
        """Get integer config value with environment variable fallback.
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default integer value if not found
            env_var: Environment variable name to check first
            
        Returns:
            Integer configuration value or fallback
        """
        # Check environment variable first
        if env_var and os.getenv(env_var):
            try:
                return int(os.getenv(env_var))
            except ValueError:
                logger.warning(f"Invalid integer in {env_var}, using fallback")
                pass
        
        # Fall back to config file
        try:
            return self.config.getint(section, key)
        except:
            return fallback
    
    def get_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured devices with environment variable support.
        
        Devices can be configured in config.ini or via environment variables.
        Environment variable format: DEVICE_<NAME>_<SETTING>
        
        Returns:
            Dictionary mapping device names to their configuration
            
        Examples:
            >>> config.get_devices()
            {'bitaxe-gamma': {'ip': '192.168.1.100', 'temp_thresholds': '60,65,70', ...}}
        """
        devices = {}
        
        # First, load from config file
        for section in self.config.sections():
            if section != "Bot":
                devices[section] = {
                    'ip': self.config.get(section, 'ip'),
                    'temp_thresholds': self.config.get(section, 'temp_thresholds', fallback=DEFAULT_TEMP_THRESHOLDS),
                    'fan_thresholds': self.config.get(section, 'fan_thresholds', fallback=DEFAULT_FAN_THRESHOLDS),
                    'volt_thresholds': self.config.get(section, 'volt_thresholds', fallback=DEFAULT_VOLT_THRESHOLDS),
                    'vr_temp_thresholds': self.config.get(section, 'vr_temp_thresholds', fallback=DEFAULT_VR_TEMP_THRESHOLDS),
                }
        
        # Then, check for environment variable overrides
        # Format: DEVICE_<name>_IP, DEVICE_<name>_TEMP_THRESHOLDS, etc.
        for env_key, env_value in os.environ.items():
            if env_key.startswith('DEVICE_') and '_IP' in env_key:
                # Extract device name
                device_name = env_key.replace('DEVICE_', '').replace('_IP', '').lower().replace('_', '-')
                
                if device_name not in devices:
                    devices[device_name] = {}
                
                devices[device_name]['ip'] = env_value
                
                # Look for other settings for this device
                prefix = f"DEVICE_{env_key.split('_IP')[0].replace('DEVICE_', '')}_"
                devices[device_name]['temp_thresholds'] = os.getenv(f"{prefix}TEMP_THRESHOLDS", DEFAULT_TEMP_THRESHOLDS)
                devices[device_name]['fan_thresholds'] = os.getenv(f"{prefix}FAN_THRESHOLDS", DEFAULT_FAN_THRESHOLDS)
                devices[device_name]['volt_thresholds'] = os.getenv(f"{prefix}VOLT_THRESHOLDS", DEFAULT_VOLT_THRESHOLDS)
                devices[device_name]['vr_temp_thresholds'] = os.getenv(f"{prefix}VR_TEMP_THRESHOLDS", DEFAULT_VR_TEMP_THRESHOLDS)
        
        return devices
    
    @property
    def project_root_path(self) -> str:
        """Get project root directory path.
        
        Returns:
            Absolute path to project root directory
        """
        return self.project_root


# Global config instance
_config = Config()


# Bot Configuration
def get_bot_token() -> str:
    """Get Discord bot token from config or environment.
    
    Returns:
        Discord bot token string
    """
    return _config.get("Bot", "token", env_var="DISCORD_BOT_TOKEN", fallback="")


def get_channel_id() -> int:
    """Get Discord channel ID from config or environment.
    
    Returns:
        Discord channel ID as integer
    """
    return _config.getint("Bot", "channel_id", env_var="DISCORD_CHANNEL_ID", fallback=0)


def get_update_interval() -> int:
    """Get update interval in seconds from config or environment.
    
    Returns:
        Update interval in seconds (default: 30)
    """
    return _config.getint("Bot", "update_interval", env_var="UPDATE_INTERVAL", fallback=DEFAULT_UPDATE_INTERVAL)


def get_mention_user_id() -> Optional[str]:
    """Get user ID to mention on new records.
    
    Returns:
        User ID string or None if not configured
    """
    value = _config.get("Bot", "mention_user_id", env_var="MENTION_USER_ID", fallback=None)
    return value if value else None


def get_project_root() -> str:
    """Get project root directory.
    
    Returns:
        Absolute path to project root
    """
    return _config.project_root_path


def get_devices() -> Dict[str, Dict[str, Any]]:
    """Get all configured devices.
    
    Returns:
        Dictionary mapping device names to their configuration
    """
    return _config.get_devices()


def get_device_config(device_name: str, key: str, fallback: str = "") -> str:
    """Get specific device configuration value.
    
    Args:
        device_name: Name of the device
        key: Configuration key to retrieve
        fallback: Default value if not found
        
    Returns:
        Configuration value or fallback
    """
    devices = get_devices()
    if device_name in devices:
        return devices[device_name].get(key, fallback)
    return fallback
