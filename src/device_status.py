"""BitAxe/NerdAxe device status fetcher with API support.

This module handles fetching and unifying status data from BitAxe and NerdAxe
mining devices via their HTTP APIs with caching support.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from src.config import get_devices

logger = logging.getLogger(__name__)

# Caching configuration
STATUS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = timedelta(seconds=5)  # Cache for 5 seconds


async def fetch_status(ip: str) -> Dict[str, Any]:
    """Fetch status from a BitAxe/NerdAxe device.
    
    Args:
        ip: IP address of the device
        
    Returns:
        Dictionary containing device status or error information
        
    Examples:
        >>> status = await fetch_status("192.168.1.100")
        >>> print(status.get('ASICModel'))
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{ip}/api/system/info", timeout=aiohttp.ClientTimeout(total=5)) as response:
                logger.debug(f"Successfully fetched data from {ip}")
                return await response.json()
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching from {ip}")
        return {"error": "timeout"}
    except aiohttp.ClientError as e:
        logger.error(f"Client error fetching from {ip}: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error fetching from {ip}: {e}")
        return {"error": str(e)}


async def get_all_device_statuses() -> Dict[str, Dict[str, Any]]:
    """Fetch status from all configured devices with caching.
    
    Returns:
        Dictionary mapping device names to their unified status data
        
    Examples:
        >>> statuses = await get_all_device_statuses()
        >>> for name, status in statuses.items():
        ...     print(f"{name}: {status.get('hashRate')}")
    """
    global STATUS_CACHE
    
    devices = get_devices()
    tasks = []
    hostnames = []
    
    for hostname, device_config in devices.items():
        if device_config.get('ip'):
            # Check cache
            if hostname in STATUS_CACHE:
                cache_entry = STATUS_CACHE[hostname]
                if datetime.now() - cache_entry['timestamp'] < CACHE_TTL:
                    logger.debug(f"Using cached status for {hostname}")
                    continue
            
            hostnames.append(hostname)
            tasks.append(fetch_status(device_config['ip']))
    
    # Fetch new data
    if tasks:
        results = await asyncio.gather(*tasks)
        for hostname, data in zip(hostnames, results):
            unified = unify_status(data, hostname)
            STATUS_CACHE[hostname] = {
                'data': unified,
                'timestamp': datetime.now()
            }
    
    # Return all cached data
    return {name: STATUS_CACHE[name]['data'] for name in devices.keys() if name in STATUS_CACHE}


def get_value(data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    """Get value from data dict, supporting nested keys.
    
    Args:
        data: Dictionary to search in
        keys: List of keys, either alternatives or nested path
        
    Returns:
        Value if found, None otherwise
        
    Examples:
        >>> data = {"stratum": {"poolMode": "solo"}}
        >>> get_value(data, ["stratum", "poolMode"])
        'solo'
        >>> get_value(data, ["power", "voltage"])  # Try alternatives
        None
    """
    if not keys:
        return None
    
    # Check if this is a nested path (multi-element list where first element is a dict in data)
    if len(keys) > 1 and keys[0] in data and isinstance(data.get(keys[0]), dict):
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current
    
    # Otherwise, try each key as an alternative
    for key in keys:
        if key in data:
            return data[key]
    return None

def unify_status(data: Dict[str, Any], hostname: str) -> Dict[str, Any]:
    """Unify BitAxe/NerdAxe API response with support for all 80+ sensors.
    
    Args:
        data: Raw API response from device
        hostname: Device hostname for logging
        
    Returns:
        Unified status dictionary with standardized keys
        
    Note:
        Supports both BitAxe (single ASIC) and NerdAxe (multi-ASIC) devices
        with full sensor coverage from AxeOS-HA-Integration specification.
    """
    if "error" in data:
        return data

    # Vereinheitlichte Struktur mit Defaults für alle möglichen API-Werte
    # Basierend auf AxeOS-HA-Integration Sensor-Definitionen
    return {
        # Basic Info
        "hostname": get_value(data, ["hostname"]) or hostname,
        "deviceID": get_value(data, ["deviceID"]) or "N/A",
        "ip": get_value(data, ["ip", "hostip"]) or "N/A",
        "mac": get_value(data, ["macAddr", "mac"]) or "N/A",
        
        # Power & Performance
        "power": get_value(data, ["power"]) or 0.0,
        "powerLimit": get_value(data, ["powerLimit"]) or 0.0,
        "maxPower": get_value(data, ["maxPower"]) or 0.0,
        "minPower": get_value(data, ["minPower"]) or 0.0,
        "voltage": get_value(data, ["voltage"]) or 0,
        "current": get_value(data, ["current"]) or 0,
        "maxVoltage": get_value(data, ["maxVoltage"]) or 0,
        "minVoltage": get_value(data, ["minVoltage"]) or 0,
        "nominalVoltage": get_value(data, ["nominalVoltage"]) or 0,
        
        # Hashrate Metrics (inkl. erweiterte NerdAxe Metriken)
        "hashRate": get_value(data, ["hashRate"]) or 0.0,
        "hashRate_1m": get_value(data, ["hashRate_1m"]) or 0.0,
        "hashRate_10m": get_value(data, ["hashRate_10m"]) or 0.0,
        "hashRate_1h": get_value(data, ["hashRate_1h"]) or 0.0,
        "hashRate_1d": get_value(data, ["hashRate_1d"]) or 0.0,
        "expectedHashrate": get_value(data, ["expectedHashrate"]) or 0.0,
        
        # Temperature
        "temp": get_value(data, ["temp"]) or 0,
        "vrTemp": get_value(data, ["vrTemp"]) or 0,
        "temptarget": get_value(data, ["temptarget", "pidTargetTemp"]) or 0,
        "overheat_temp": get_value(data, ["overheat_temp"]) or 0,
        
        # Mining Statistics
        "bestDiff": get_value(data, ["bestDiff"]) or "-",
        "bestSessionDiff": get_value(data, ["bestSessionDiff"]) or "-",
        "bestDiffTime": get_value(data, ["bestDiffTime"]) or "-",
        "poolDifficulty": get_value(data, ["poolDifficulty"]) or 0,
        "stratumDifficulty": get_value(data, ["stratumDifficulty"]) or 0,
        "sharesAccepted": get_value(data, ["sharesAccepted"]) or 0,
        "sharesRejected": get_value(data, ["sharesRejected"]) or 0,
        "sharesRejectedReasons": get_value(data, ["sharesRejectedReasons"]) or [],
        
        # Voltage & Frequency
        "coreVoltage": get_value(data, ["coreVoltage"]) or 0,
        "defaultCoreVoltage": get_value(data, ["defaultCoreVoltage"]) or 0,
        "coreVoltageActual": get_value(data, ["coreVoltageActual", "coreVoltageActualMV"]) or 0,
        "coreVoltageSet": get_value(data, ["coreVoltageSet"]) or 0,
        "frequency": get_value(data, ["frequency"]) or 0,
        
        # Network
        "ssid": get_value(data, ["ssid"]) or "-",
        "wifiStatus": get_value(data, ["wifiStatus"]) or "-",
        "wifiRSSI": get_value(data, ["wifiRSSI"]) or 0,
        
        # Hardware Info
        "ASICModel": get_value(data, ["ASICModel"]) or "Unknown",
        "deviceModel": get_value(data, ["deviceModel", "boardVersion"]) or "Unknown",
        "asicCount": get_value(data, ["asicCount"]) or 0,
        "smallCoreCount": get_value(data, ["smallCoreCount"]) or 0,
        
        # Fan Control
        "fanspeed": get_value(data, ["fanspeed"]) or 0,
        "fanrpm": get_value(data, ["fanrpm"]) or 0,
        "manualFanSpeed": get_value(data, ["manualFanSpeed"]) or 0,
        
        # System Info
        "uptimeSeconds": get_value(data, ["uptimeSeconds"]) or 0,
        "freeHeap": get_value(data, ["freeHeap"]) or 0,
        "freeHeapInt": get_value(data, ["freeHeapInt"]) or 0,
        "version": get_value(data, ["version"]) or "N/A",
        "axeOSVersion": get_value(data, ["axeOSVersion"]) or "N/A",
        "idfVersion": get_value(data, ["idfVersion"]) or "N/A",
        "boardVersion": get_value(data, ["boardVersion", "deviceModel"]) or "Unknown",
        
        # Stratum
        "stratumURL": get_value(data, ["stratumURL"]) or "-",
        "stratumPort": get_value(data, ["stratumPort"]) or "-",
        "stratumUser": get_value(data, ["stratumUser"]) or "-",
        "fallbackStratumURL": get_value(data, ["fallbackStratumURL"]) or "-",
        "fallbackStratumPort": get_value(data, ["fallbackStratumPort"]) or "-",
        "fallbackStratumUser": get_value(data, ["fallbackStratumUser"]) or "-",
        "isUsingFallbackStratum": get_value(data, ["isUsingFallbackStratum", "stratum.usingFallback"]) or False,
        
        # NerdAxe Specific
        "duplicateHWNonces": get_value(data, ["duplicateHWNonces"]) or 0,
        "foundBlocks": get_value(data, ["foundBlocks"]) or 0,
        "totalFoundBlocks": get_value(data, ["totalFoundBlocks"]) or 0,
        "defaultFrequency": get_value(data, ["defaultFrequency"]) or 0,
        "vrFrequency": get_value(data, ["vrFrequency"]) or 0,
        "defaultVrFrequency": get_value(data, ["defaultVrFrequency"]) or 0,
        "jobInterval": get_value(data, ["jobInterval"]) or 0,
        "lastResetReason": get_value(data, ["lastResetReason"]) or "N/A",
        "runningPartition": get_value(data, ["runningPartition"]) or "N/A",
        
        # PID Controller Values (NerdAxe)
        "pidP": get_value(data, ["pidP"]) or 0,
        "pidI": get_value(data, ["pidI"]) or 0,
        "pidD": get_value(data, ["pidD"]) or 0,
        
        # Stratum Pool Details (verschachtelt für NerdAxe)
        "stratum_poolMode": get_value(data, ["stratum", "poolMode"]) or "-",
        "stratum_activePoolMode": get_value(data, ["stratum", "activePoolMode"]) or "-",
        "stratum_poolBalance": get_value(data, ["stratum", "poolBalance"]) or 0,
        "stratum_totalBestDiff": get_value(data, ["stratum", "totalBestDiff"]) or 0,
        "stratum_poolDifficulty": get_value(data, ["stratum", "poolDifficulty"]) or 0,
        
        # Binary Sensor Values
        "overheat_mode": get_value(data, ["overheat_mode"]) or False,
        "autofanspeed": get_value(data, ["autofanspeed"]) or False,
        "invertfanpolarity": get_value(data, ["invertfanpolarity"]) or False,
        "flipscreen": get_value(data, ["flipscreen"]) or False,
        "invertscreen": get_value(data, ["invertscreen"]) or False,
    }
