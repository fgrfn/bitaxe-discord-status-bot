import discord
from src.device_status import get_all_device_statuses
import json
import os
from datetime import datetime
import logging
import time
import threading
from src.config import get_project_root, get_update_interval, get_mention_user_id, get_devices, get_device_config

# Absolute Pfade für Dateien
PROJECT_ROOT = get_project_root()
BEST_DIFF_FILE = os.path.join(PROJECT_ROOT, "data", "best_difficulty.json")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "bitaxe.log")

# Lock für Thread-sichere Datei-Operationen
file_lock = threading.Lock()

# Lade den Update-Intervall aus der Konfiguration
update_interval = get_update_interval()


def get_mention_id():
    """Get mention user ID from config."""
    return get_mention_user_id()


def get_version() -> str:
    """Read version from VERSION file.
    
    Returns:
        Version string (e.g., '2.0.0') or 'unknown' if file not found
    """
    try:
        version_file = os.path.join(PROJECT_ROOT, 'VERSION')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return 'unknown'
    except Exception:
        return 'unknown'

# Lade die Best-Difficulty-Historie nur einmal beim Start oder bei einer Änderung
best_diff_history = []

# Logging konfigurieren mit Rotation
from logging.handlers import RotatingFileHandler
logger = logging.getLogger("bitaxe")
logger.setLevel(logging.INFO)

# File Handler mit Rotation (max 5MB, 3 Backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def format_uptime(seconds):
    """Format uptime in days, hours, minutes."""
    if seconds < 60:
        return f"{seconds}s"
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d {hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m {secs}s"

def get_vr_temp(status):
    vr_temp = status.get('vrTemp', 0)
    if vr_temp == 0:
        return "n/v"
    return f"{vr_temp}°C"

def get_vr_temp_emoji(vr_temp, thresholds, emojis):
    """ Gibt die Ampel für VR-Temperatur zurück, basierend auf den Schwellenwerten """
    if vr_temp == "n/v":
        return ""  # Keine Ampel, wenn der Wert "n/v" ist
    vr_temp = float(vr_temp)
    if vr_temp < thresholds[0]:
        return emojis[0]  # Grün
    elif vr_temp < thresholds[1]:
        return emojis[1]  # Gelb
    else:
        return emojis[2]  # Rot

def get_temp_emoji(value, temp_thresholds, temp_emojis):
    if value < temp_thresholds[0]:
        return temp_emojis[0]  # Grün
    elif value < temp_thresholds[1]:
        return temp_emojis[1]  # Gelb
    else:
        return temp_emojis[2]  # Rot

def get_fan_emoji(value, fan_thresholds, fan_emojis):
    if value <= fan_thresholds[0]:
        return fan_emojis[2]  # Rot
    elif value <= fan_thresholds[1]:
        return fan_emojis[1]  # Gelb
    else:
        return fan_emojis[0]  # Grün

def get_wifi_emoji(rssi):
    """Get WiFi signal strength emoji based on RSSI."""
    if rssi == 0:
        return "❌"
    elif rssi >= -50:
        return "🟢"  # Excellent
    elif rssi >= -60:
        return "🟢"  # Good
    elif rssi >= -70:
        return "🟡"  # Fair
    else:
        return "🔴"  # Weak

def format_ram(free_heap):
    """Format RAM in KB or MB."""
    if free_heap >= 1024:
        return f"{free_heap / 1024:.1f} MB"
    else:
        return f"{free_heap} KB"

def calculate_share_success_rate(accepted, rejected):
    """Calculate share success rate."""
    total = accepted + rejected
    if total == 0:
        return 100.0
    return (accepted / total) * 100

def get_volt_emoji(value, thresholds, emojis):
    if value >= thresholds[2]:
        return emojis[2]  # rot
    elif value >= thresholds[1]:
        return emojis[1]  # gelb
    else:
        return emojis[0]  # grün

def load_best_diff():
    global best_diff_history
    if not best_diff_history:  # Wenn noch keine Daten geladen sind
        if os.path.exists(BEST_DIFF_FILE):
            try:
                with file_lock:
                    with open(BEST_DIFF_FILE, "r") as f:
                        best_diff_history = json.load(f)
                        logger.info(f"Best-Difficulty Historie geladen: {best_diff_history}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Fehler beim Laden der Best-Difficulty: {e}")
                best_diff_history = {}
        else:
            logger.info("Best-Difficulty Datei existiert nicht oder ist leer.")
    return best_diff_history

def check_and_update_best_diff(status):
    current_best = load_best_diff()
    new_record = False
    new_record_value = None
    
    try:
        # Neue Best-Difficulty prüfen
        best_diff_str = str(status['bestDiff'])
        if not best_diff_str or best_diff_str == '-':
            return new_record, new_record_value
            
        val_str = best_diff_str.lower().replace("g", "e9").replace("m", "e6").replace("k", "e3")
        numeric_val = int(float(val_str))
        
        if not current_best or numeric_val > int(current_best.get('value', 0)):
            save_best_diff(numeric_val, status['bestDiff'], status['hostname'])
            new_record = True
            new_record_value = format_best_diff(status['bestDiff'])
    except (ValueError, TypeError) as e:
        logger.warning(f"Fehler beim Parsen von bestDiff '{status.get('bestDiff')}': {e}")

    return new_record, new_record_value

def save_best_diff(value, best_diff, hostname):
    # Extrahiere das Suffix (G/M/K) sicher
    suffix = 'G'  # Default
    best_diff_str = str(best_diff).upper()
    if best_diff_str and len(best_diff_str) > 0:
        last_char = best_diff_str[-1]
        if last_char in ['G', 'M', 'K']:
            suffix = last_char
    
    best = {
        "value": value,
        "short": suffix,
        "hostname": hostname,
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        with file_lock:
            with open(BEST_DIFF_FILE, "w") as f:
                json.dump(best, f, indent=2)
        logger.info(f"🏆 Neuer Best-Difficulty gespeichert: {best_diff} von {hostname}")
    except IOError as e:
        logger.error(f"Fehler beim Speichern der Best-Difficulty: {e}")

def get_best_diff_suffix(best_diff):
    best_diff_str = str(best_diff).strip().upper()
    if best_diff_str and best_diff_str[-1] in ["G", "M", "K"]:
        return best_diff_str[-1]
    return ""

def format_best_diff(best_diff):
    try:
        best_diff_str = str(best_diff).strip().upper()
        # Umwandlung der Best-Difficulty in ein numerisches Format
        if 'G' in best_diff_str:  # Falls es sich um Gigabytes handelt
            value = float(best_diff_str.replace('G', '').strip()) * 1e9
            formatted_value = f"{int(value):,} (G)"
        elif 'M' in best_diff_str:  # Falls es sich um Megabytes handelt
            value = float(best_diff_str.replace('M', '').strip()) * 1e6
            formatted_value = f"{int(value):,} (M)"
        elif 'K' in best_diff_str:  # Falls es sich um Kilobytes handelt
            value = float(best_diff_str.replace('K', '').strip()) * 1e3
            formatted_value = f"{int(value):,} (K)"
        else:
            value = float(best_diff_str)
            formatted_value = f"{int(value):,}"
        return formatted_value
    except Exception as e:
        logger.error(f"Fehler bei der Formatierung der Best-Difficulty: {e}")
        return str(best_diff)  # Falls etwas schief geht, einfach den Originalwert zurückgeben

def chunk_embed_field(value, max_length=1024):
    if value.startswith("```") and value.endswith("```"):
        code_fence = value.split("\n", 1)[0]
        inner = value[len(code_fence) + 1:-3]
        chunks = [inner[i:i + max_length - len(code_fence) - 4] for i in range(0, len(inner), max_length - len(code_fence) - 4)]
        return [f"{code_fence}\n{chunk}```" for chunk in chunks]
    return [value[i:i + max_length] for i in range(0, len(value), max_length)]

def add_spacer_field(embed):
    embed.add_field(name="\u200b", value="\u200b", inline=False)

def build_summary(data):
    total_devices = len(data)
    online_devices = sum(1 for s in data.values() if "error" not in s)
    offline_devices = total_devices - online_devices
    total_hashrate = sum(s.get('hashRate', 0) for s in data.values() if "error" not in s)
    total_power = sum(s.get('power', 0) for s in data.values() if "error" not in s)
    total_efficiency = total_hashrate / total_power if total_power > 0 else 0
    return total_devices, online_devices, offline_devices, total_hashrate, total_power, total_efficiency

async def format_status_embeds():
    data = await get_all_device_statuses()
    current_best = load_best_diff()  # Lade die Best-Difficulty-Historie nur einmal
    new_record = False
    new_record_value = None
    best_diff_history = []  # History der Best-Difficulty

    # Formatierte Zeitangabe für "Vor"
    def format_time_ago(minutes):
        days, remainder = divmod(minutes, 1440)  # 1440 Minuten = 1 Tag
        hours, minutes = divmod(remainder, 60)  # 60 Minuten = 1 Stunde
        time_ago = ""
        if days > 0:
            time_ago += f"{days} Tage "
        if hours > 0:
            time_ago += f"{hours} Stunden "
        if minutes > 0:
            time_ago += f"{minutes} Minuten"
        return time_ago.strip()

    # Berechnung der Zeitdifferenz in Minuten
    for hostname, status in data.items():
        if "error" in status:
            continue

        try:
            # Überprüfe und speichere Best-Difficulty nur bei Änderung
            is_new_record, record_value = check_and_update_best_diff(status)
            if is_new_record:
                new_record = True
                new_record_value = record_value
            
            val_str = str(status['bestDiff']).lower().replace("g", "e9").replace("m", "e6").replace("k", "e3")
            numeric_val = int(float(val_str))

            # Füge den aktuellen Best-Difficulty zur Historie hinzu
            best_diff_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "value": status['bestDiff'],
                "short": get_best_diff_suffix(status['bestDiff']),
                "hostname": hostname
            })

        except Exception as e:
            logger.warning(f"Fehler beim Parsen von BestDiff für {hostname}: {e}")
            continue

    bitaxe_embed = discord.Embed(title="📡 BitAxe Geräteübersicht", color=discord.Color.green())
    nerdaxe_embed = discord.Embed(title="📡 NerdAxe Geräteübersicht", color=discord.Color.blue())
    history_embed = discord.Embed(title="🏆 Best-Difficulty Historie", color=discord.Color.gold())
    add_spacer_field(bitaxe_embed)
    add_spacer_field(nerdaxe_embed)
    add_spacer_field(history_embed)

    bitaxe_data = {}
    nerdaxe_data = {}

    sorted_data = sorted(data.items(), key=lambda x: x[0])
    devices = get_devices()

    device_entries = []
    for hostname, status in sorted_data:
        if "error" in status:
            is_nerdaxe = "nerd" in hostname.lower()
            device_entries.append((hostname, status, is_nerdaxe, True))
            if is_nerdaxe:
                nerdaxe_data[hostname] = status
            else:
                bitaxe_data[hostname] = status
            continue

        is_nerdaxe = status.get('vrFrequency', 0) > 0 or status.get('jobInterval', 0) > 0
        device_entries.append((hostname, status, is_nerdaxe, False))
        if is_nerdaxe:
            nerdaxe_data[hostname] = status
        else:
            bitaxe_data[hostname] = status
    bitaxe_stats = build_summary(bitaxe_data)
    nerdaxe_stats = build_summary(nerdaxe_data)

    for embed, stats in ((bitaxe_embed, bitaxe_stats), (nerdaxe_embed, nerdaxe_stats)):
        total_devices, online_devices, offline_devices, total_hashrate, total_power, total_efficiency = stats
        summary = (
            f"```ansi\n"
            f"📊 Gesamt: {total_devices} Gerät{'e' if total_devices != 1 else ''} | "
            f"🟢 {online_devices} Online | 🔴 {offline_devices} Offline\n"
            f"⚡ Total : {total_hashrate:.2f} GH/s | 🔋 {total_power:.2f}W | "
            f"📈 {total_efficiency:.2f} GH/W\n"
            f"```"
        )
        embed.add_field(name="📊 Übersicht", value=summary, inline=False)

    for hostname, status, is_nerdaxe, is_error in device_entries:
        target_embed = nerdaxe_embed if is_nerdaxe else bitaxe_embed
        if is_error:
            target_embed.add_field(
                name=f"❌ {hostname}",
                value=f"Fehler beim Abrufen: `{status['error']}`",
                inline=False
            )
            continue

        device_config = devices.get(hostname, {})
        ip = device_config.get('ip', status['ip'])

        # Spannung bleibt in mV
        voltage = status.get('voltage', 1000)  # Spannung bleibt in mV

        # Schwellenwerte aus Konfiguration (mit Validierung)
        try:
            vr_temp_thresholds = list(map(int, device_config.get('vr_temp_thresholds', '50,60,70').split(',')))
            temp_thresholds = list(map(int, device_config.get('temp_thresholds', '50,60,70').split(',')))
            fan_thresholds = list(map(int, device_config.get('fan_thresholds', '0,2000,3500,7500').split(',')))
            volt_thresholds = list(map(float, device_config.get('volt_thresholds', '1.0,1.2,1.4').split(',')))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Fehler beim Parsen der Schwellenwerte für {hostname}: {e}. Verwende Defaults.")
            vr_temp_thresholds = [50, 60, 70]
            temp_thresholds = [50, 60, 70]
            fan_thresholds = [0, 2000, 3500, 7500]
            volt_thresholds = [1.0, 1.2, 1.4]

        # VR-Temperatur-Ampel
        vr_temp_emoji = get_vr_temp_emoji(status['vrTemp'], vr_temp_thresholds, ["🟢", "🟡", "🔴"])
        temp_emoji = get_temp_emoji(status['temp'], temp_thresholds, ["🟢", "🟡", "🔴"])
        fan_emoji = get_fan_emoji(status['fanrpm'], fan_thresholds, ["🟢", "🟡", "🔴"])
        volt_emoji = get_volt_emoji(voltage, volt_thresholds, ["🟢", "🟡", "🔴"])
        
        # WiFi-Info
        wifi_rssi = status.get('wifiRSSI', 0)
        wifi_ssid = status.get('ssid', '-')
        wifi_emoji = get_wifi_emoji(wifi_rssi)
        
        # System-Info
        uptime_str = format_uptime(status.get('uptimeSeconds', 0))
        free_heap = status.get('freeHeap', 0)
        ram_str = format_ram(free_heap)
        version_str = status.get('version', 'N/A')
        
        # Share-Erfolgsrate
        accepted = status.get('sharesAccepted', 0)
        rejected = status.get('sharesRejected', 0)
        success_rate = calculate_share_success_rate(accepted, rejected)
        
        # Expected Hashrate (falls vorhanden)
        expected_hr = status.get('expectedHashrate', 0)
        
        # Power Limits
        min_power = status.get('minPower', 0)
        max_power = status.get('maxPower', 0)
        power_limit = status.get('powerLimit', 0)
        
        # Voltage Limits
        min_voltage = status.get('minVoltage', 0)
        max_voltage = status.get('maxVoltage', 0)
        
        # Overheat Protection
        overheat_mode = status.get('overheat_mode', False)
        overheat_temp = status.get('overheat_temp', 0)
        temp_target = status.get('temptarget', 0)
        
        # Hashrate-Metriken (erweitert für NerdAxe)
        hashrate_section = f"⚡ Hashrate  : 🔥 **{status['hashRate']:.2f} GH/s** 🔥\n"
        
        # Expected vs Actual Hashrate
        if expected_hr > 0:
            actual_percent = (status['hashRate'] / expected_hr) * 100
            hashrate_section += f"🎯 Expected : {expected_hr:.1f} GH/s ({actual_percent:.1f}%)\n"
        
        if is_nerdaxe:
            # NerdAxe: Zeige erweiterte Hashrate-Metriken
            hr_1m = status.get('hashRate_1m', 0)
            hr_10m = status.get('hashRate_10m', 0)
            hr_1h = status.get('hashRate_1h', 0)
            hr_1d = status.get('hashRate_1d', 0)
            if hr_1m > 0 or hr_10m > 0 or hr_1h > 0:
                hashrate_section += f"📊 Avg 1m/10m/1h: {hr_1m:.1f} / {hr_10m:.1f} / {hr_1h:.1f} GH/s\n"
                if hr_1d > 0:
                    hashrate_section += f"📊 Avg 24h    : {hr_1d:.1f} GH/s\n"
        
        # NerdAxe-spezifische Statistiken
        nerdaxe_stats = ""
        if is_nerdaxe:
            found_blocks = status.get('foundBlocks', 0)
            total_blocks = status.get('totalFoundBlocks', 0)
            dup_nonces = status.get('duplicateHWNonces', 0)
            if found_blocks > 0 or total_blocks > 0:
                nerdaxe_stats = (
                    f"#########################\n"
                    f"# NerdAxe Statistiken   #\n"
                    f"#########################\n"
                    f"🏆 Blocks (Session): {found_blocks}\n"
                    f"🏆 Blocks (Total)  : {total_blocks}\n"
                )
                if dup_nonces > 0:
                    nerdaxe_stats += f"⚠️ Duplicate Nonces: {dup_nonces}\n"
            
            # PID Controller (NerdAxe)
            pid_p = status.get('pidP', 0)
            pid_i = status.get('pidI', 0)
            pid_d = status.get('pidD', 0)
            if pid_p > 0 or pid_i > 0 or pid_d > 0:
                nerdaxe_stats += (
                    f"🎛️ PID (P/I/D)   : {pid_p:.2f} / {pid_i:.2f} / {pid_d:.2f}\n"
                )
        
        value = (
            f"```ansi\n"
            f"##########################\n"
            f"# Hardware-Informationen #\n"
            f"##########################\n"
            f"\n"  # Added blank line here

            f"🖥️ ASICModel : {status['ASICModel']}\n"
            f"🧭 Frequency : {status['frequency']} MHz @{status['coreVoltageActual']/1000:.3f}V | {status['coreVoltage']/1000:.3f}V\n"
            f"🔧 Device    : {status.get('deviceModel', 'Unknown')}\n"
            f"⏰ Uptime    : {uptime_str}\n"
            f"🧠 Free RAM  : {ram_str}\n"
            f"📦 Version   : {version_str}\n"
            f"🌐 WiFi      : {wifi_ssid} ({wifi_rssi} dBm) {wifi_emoji}\n"
            f"📍 IP/MAC    : {ip} | {status.get('mac', 'N/A')}\n"
        )
        
        # Overheat Protection Status
        if temp_target > 0:
            value += f" (Target: {temp_target}°C)\n"
        else:
            value += "\n"
        
        if overheat_temp > 0:
            overheat_status = "🟢 Aus" if not overheat_mode else "🔴 Aktiv"
            value += f"🛡️ Overheat  : {overheat_status} (Grenze: {overheat_temp}°C)\n"
        
        value += (
            f"🔌 VR Temp   : {get_vr_temp(status)} {vr_temp_emoji}\n"
            f"🔋 Power     : {status['power']:.2f} W @ {voltage/1000:.3f} V\n"
        )
        
        # Power Limits (falls verfügbar)
        if min_power > 0 or max_power > 0:
            value += f"⚡ Limits    : {min_power:.1f}W - {max_power:.1f}W"
            if power_limit > 0:
                value += f" (Limit: {power_limit:.1f}W)"
            value += "\n"
        
        # Voltage Limits (falls verfügbar)
        if min_voltage > 0 or max_voltage > 0:
            value += f"📊 Volt Range: {min_voltage/1000:.3f}V - {max_voltage/1000:.3f}V\n"
        
        value += (
            f"📈 Eff       : {status['hashRate'] / status['power'] if status['power'] > 0 else 0:.2f} GH/W\n"
            f"💨 Fan       : {status.get('fanspeed', 0)}% / {status['fanrpm']} RPM {fan_emoji}\n"

            f"#########################\n"
            f"# Stratum-Informationen #\n"
            f"#########################\n"
            f"🌐 Stratum   : {status['stratumURL']}:{status['stratumPort']} {'✅' if not status.get('isUsingFallbackStratum', False) else '❌'}\n"
            f"⚠️ Fallback  : {status['fallbackStratumURL']}:{status['fallbackStratumPort']} {'✅' if status.get('isUsingFallbackStratum', False) else '❌'}\n"
            f"👤 User      : {status['stratumUser']}\n"
        )
        
        # NerdAxe: Pool-Details anzeigen
        if is_nerdaxe:
            pool_mode = status.get('stratum_poolMode', '-')
            pool_balance = status.get('stratum_poolBalance', 0)
            if pool_mode != '-':
                value += f"🎱 Pool Mode : {pool_mode}\n"
                if pool_balance > 0:
                    value += f"⚖️ Balance   : {pool_balance}\n"
        
        value += "```"

        value_chunks = chunk_embed_field(value)
        target_embed = nerdaxe_embed if is_nerdaxe else bitaxe_embed
        for index, chunk in enumerate(value_chunks):
            field_name = f"🛠️ {hostname}"
            if index > 0:
                field_name = f"🛠️ {hostname} (Fortsetzung {index + 1})"
            target_embed.add_field(name=field_name, value=chunk, inline=False)

    if current_best:
        add_spacer_field(history_embed)
        timestamp = datetime.fromisoformat(current_best['timestamp'])
        minutes_ago = int((datetime.utcnow() - timestamp).total_seconds() // 60)
        formatted_time_ago = format_time_ago(minutes_ago)  # Zeit in Tagen, Stunden, Minuten formatieren
        record_block = (
            f"```ansi\n"
            f"💎 Wert      : {int(current_best['value']):,} ({current_best['short']}).\n"
            f"🛠️ Gerät     : {current_best['hostname']}\n"
            f"🕒 Zeit      : {timestamp.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏱️ Vor       : {formatted_time_ago}\n"
            f"```"
        )
        title = "🏆 Rekord-Difficulty"
        if new_record and MENTION_ID:
            title += f" – <@{MENTION_ID}> Neuer Rekord!"
        history_embed.add_field(name=title, value=record_block, inline=False)

    # Best-Difficulty Historie unter den Geräten
    if best_diff_history:
        history_header = "```ansi\nRank | 📅 Date              | 💎 BestDiff             | 🖥️ Device\n" + "-"*65 + "\n"
        history_footer = "```"
        history_lines = []
        for i, entry in enumerate(best_diff_history, 1):
            rank = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else str(i)
            best_diff_short = entry['short'] or get_best_diff_suffix(entry['value'])
            history_lines.append(
                f"{rank}   | {datetime.fromisoformat(entry['timestamp']).strftime('%d.%m.%Y %H:%M').ljust(20)} | "
                f"{entry['value']} ({best_diff_short})          | {entry['hostname']}\n"
            )
        history_message = history_header
        for line in history_lines:
            if len(history_message) + len(line) + len(history_footer) > 1024:
                break
            history_message += line
        history_message += history_footer
        history_embed.add_field(name="🏆 Best-Difficulty Historie", value=history_message, inline=False)
    else:
        history_embed.add_field(name="🏆 Best-Difficulty Historie", value="Es gibt noch keine Best-Difficulty-Historie.", inline=False)

    # Berechne verbleibende Zeit bis zum nächsten Update
    try:
        time_until_next_update = update_interval - (int(time.time()) % update_interval)
        if time_until_next_update <= 0:
            time_until_next_update = update_interval
        minutes_left = time_until_next_update // 60
        seconds_left = time_until_next_update % 60
        next_update_time = f"⏳ Nächstes Update in {minutes_left}m {seconds_left}s"
    except Exception:
        next_update_time = f"⏳ Update-Intervall: {update_interval}s"

    # Footer mit Restzeit zur nächsten Aktualisierung und Version
    version = get_version()
    bitaxe_embed.set_footer(text=f"🔁 Aktualisiert automatisch • {next_update_time} • v{version} • BitAxe Discord Bot by xNookie")
    nerdaxe_embed.set_footer(text=f"🔁 Aktualisiert automatisch • {next_update_time} • v{version} • BitAxe Discord Bot by xNookie")
    history_embed.set_footer(text=f"🔁 Aktualisiert automatisch • {next_update_time} • v{version} • BitAxe Discord Bot by xNookie")

    return {
        "bitaxe": bitaxe_embed,
        "nerdaxe": nerdaxe_embed,
        "history": history_embed,
    }, new_record, new_record_value
