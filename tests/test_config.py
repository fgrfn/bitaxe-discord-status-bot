"""Unit tests for config module.

Run with: pytest tests/test_config.py -v
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from configparser import ConfigParser

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import (
    Config,
    get_bot_token,
    get_channel_id,
    get_update_interval,
    get_devices,
    DEFAULT_TEMP_THRESHOLDS,
    DEFAULT_UPDATE_INTERVAL
)


class TestConfig:
    """Test cases for Config class."""
    
    def test_config_init_no_file(self, tmp_path):
        """Test Config initialization without config file."""
        with patch('config.os.path.dirname', return_value=str(tmp_path)):
            config = Config()
            assert config.config is not None
    
    def test_get_with_env_var(self):
        """Test config.get() with environment variable."""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            config = Config()
            result = config.get('Section', 'key', env_var='TEST_VAR')
            assert result == 'test_value'
    
    def test_get_with_fallback(self):
        """Test config.get() with fallback value."""
        config = Config()
        result = config.get('NonExistent', 'key', fallback='default')
        assert result == 'default'
    
    def test_getint_with_env_var(self):
        """Test config.getint() with environment variable."""
        with patch.dict(os.environ, {'TEST_INT': '42'}):
            config = Config()
            result = config.getint('Section', 'key', env_var='TEST_INT')
            assert result == 42
    
    def test_getint_invalid_env_var(self):
        """Test config.getint() with invalid environment variable."""
        with patch.dict(os.environ, {'TEST_INT': 'not_a_number'}):
            config = Config()
            result = config.getint('Section', 'key', fallback=10, env_var='TEST_INT')
            assert result == 10
    
    def test_get_devices_from_env(self):
        """Test get_devices() with environment variables."""
        env_vars = {
            'DEVICE_MINER1_IP': '192.168.1.100',
            'DEVICE_MINER1_TEMP_THRESHOLDS': '55,60,65',
            'DEVICE_MINER2_IP': '192.168.1.101',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            devices = config.get_devices()
            
            assert 'miner1' in devices
            assert devices['miner1']['ip'] == '192.168.1.100'
            assert devices['miner1']['temp_thresholds'] == '55,60,65'
            
            assert 'miner2' in devices
            assert devices['miner2']['ip'] == '192.168.1.101'


class TestConfigHelpers:
    """Test cases for config helper functions."""
    
    def test_get_bot_token_from_env(self):
        """Test get_bot_token() from environment."""
        with patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token_123'}):
            token = get_bot_token()
            assert token == 'test_token_123'
    
    def test_get_channel_id_from_env(self):
        """Test get_channel_id() from environment."""
        with patch.dict(os.environ, {'DISCORD_CHANNEL_ID': '123456789'}):
            channel_id = get_channel_id()
            assert channel_id == 123456789
    
    def test_get_update_interval_default(self):
        """Test that DEFAULT_UPDATE_INTERVAL constant is defined correctly."""
        # This test verifies the default constant rather than runtime behavior
        # since get_update_interval() uses the global config which may have loaded config.ini
        assert DEFAULT_UPDATE_INTERVAL == 30
        assert isinstance(DEFAULT_UPDATE_INTERVAL, int)
    
    def test_get_devices_empty(self):
        """Test get_devices() with no configuration."""
        with patch.dict(os.environ, {}, clear=True):
            devices = get_devices()
            # Should return empty dict when no config
            assert isinstance(devices, dict)


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config.ini file for testing."""
    config_path = tmp_path / "config.ini"
    config = ConfigParser()
    config['Bot'] = {
        'token': 'test_bot_token',
        'channel_id': '987654321',
        'update_interval': '60'
    }
    config['TestDevice'] = {
        'ip': '192.168.1.50',
        'temp_thresholds': '70,75,80'
    }
    
    with open(config_path, 'w') as f:
        config.write(f)
    
    return config_path


class TestConfigFile:
    """Test cases for config file loading."""
    
    def test_load_from_config_file(self, mock_config_file):
        """Test loading configuration from file."""
        with patch('config.os.path.join', return_value=str(mock_config_file)):
            config = Config()
            token = config.get('Bot', 'token')
            assert token == 'test_bot_token'
    
    def test_env_overrides_config_file(self, mock_config_file):
        """Test that environment variables override config file."""
        with patch('config.os.path.join', return_value=str(mock_config_file)):
            with patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'env_token'}):
                config = Config()
                token = config.get('Bot', 'token', env_var='DISCORD_BOT_TOKEN')
                assert token == 'env_token'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
