#!/usr/bin/env python3
"""
Touch Logger + Recorder + Macro Player - ULTIMATE EDITION
Multi-touch, Hold, Dark Mode, Universal Android Support
Features: Recording, Playback, Profiles, Analytics, Plugins, Visual Gesture Map
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import subprocess
import threading
import queue
import json
import time
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict, Callable
import math
import random
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import sys

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

HOTKEYS = {
    'record': '<F9>',
    'stop': '<F10>',
    'play': '<F11>',
    'theme': '<F12>'
}

VERSION = "4.1 Ultimate - Smart Cache Edition"

# ============================================================================
# DEVICE CACHE MANAGER
# ============================================================================

class DeviceCache:
    """Manages persistent caching of touch device IDs per phone"""
    
    def __init__(self, cache_file: Path = Path("device_cache.json")):
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                print(f"✓ Loaded device cache: {len(self.cache)} devices")
            except Exception as e:
                print(f"Warning: Could not load cache: {e}")
                self.cache = {}
        else:
            self.cache = {}
    
    def _save(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")
    
    def get(self, device_fingerprint: str) -> Optional[str]:
        """Get cached touch device for a phone"""
        if device_fingerprint in self.cache:
            return self.cache[device_fingerprint].get('touch_device')
        return None
    
    def set(self, device_fingerprint: str, touch_device: str):
        """Cache touch device for a phone"""
        self.cache[device_fingerprint] = {
            'touch_device': touch_device,
            'last_used': datetime.now().isoformat()
        }
        self._save()
        print(f"✓ Cached: {device_fingerprint} → {touch_device}")
    
    def exists(self, device_fingerprint: str) -> bool:
        """Check if device is in cache"""
        return device_fingerprint in self.cache
    
    def remove(self, device_fingerprint: str):
        """Remove device from cache"""
        if device_fingerprint in self.cache:
            del self.cache[device_fingerprint]
            self._save()

# ============================================================================
# THEME MANAGER
# ============================================================================

class ThemeManager:
    """Manages dark and light themes for the application"""

    DARK = {
        'bg': '#1e1e1e', 'fg': '#e0e0e0', 'text_bg': '#2d2d2d',
        'text_fg': '#e0e0e0', 'select_bg': '#0078d7', 'accent': '#4da6ff',
        'success': '#6bb344', 'error': '#f1707b', 'warning': '#ffa800',
        'chart_bg': '#1e1e1e', 'chart_grid': '#3e3e3e'
    }

    LIGHT = {
        'bg': '#f0f0f0', 'fg': '#000000', 'text_bg': '#ffffff',
        'text_fg': '#000000', 'select_bg': '#0078d7', 'accent': '#0078d7',
        'success': '#107c10', 'error': '#e81123', 'warning': '#ff8c00',
        'chart_bg': '#ffffff', 'chart_grid': '#e0e0e0'
    }

    def __init__(self):
        self.is_dark = True
        self.current = self.DARK.copy()

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TouchEvent:
    """Represents a single touch event from the device"""
    timestamp: float
    x: int
    y: int
    event_type: str  # DOWN, MOVE, UP
    slot: int = 0

@dataclass
class TouchAction:
    """Represents a complete touch action/gesture"""
    action_type: str  # TAP, SWIPE, HOLD, MULTI_TAP
    start_x: int
    start_y: int
    end_x: Optional[int] = None
    end_y: Optional[int] = None
    duration: float = 0.0
    timestamp: float = 0.0
    delay_before: float = 0.0
    slot: int = 0
    secondary_fingers: List[Tuple[int, int]] = None
    humanize: bool = False  # Add random jitter for more natural playback

    def __post_init__(self):
        if self.secondary_fingers is None:
            self.secondary_fingers = []

@dataclass
class Macro:
    """Represents a recorded macro sequence"""
    name: str
    actions: List[TouchAction]
    device_width: int
    device_height: int
    created_at: str
    description: str = ""
    loop_count: int = 1
    gesture_name: str = ""  # Named gesture type

@dataclass
class Profile:
    """Represents a device profile with settings"""
    name: str
    device_id: str
    screen_width: int
    screen_height: int
    touch_device: str
    macros: List[str]  # List of macro names
    created_at: str

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Manages persistent storage of macros, profiles, and analytics"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()

        # Macros table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                device_width INTEGER,
                device_height INTEGER,
                created_at TEXT,
                description TEXT,
                gesture_name TEXT,
                data TEXT
            )
        ''')

        # Profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                device_id TEXT,
                screen_width INTEGER,
                screen_height INTEGER,
                touch_device TEXT,
                macros TEXT,
                created_at TEXT
            )
        ''')

        # Analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                macro_name TEXT,
                play_count INTEGER DEFAULT 0,
                total_duration REAL,
                avg_delay REAL,
                last_played TEXT
            )
        ''')

        self.conn.commit()

    def save_macro(self, macro: Macro):
        """Save a macro to the database"""
        cursor = self.conn.cursor()
        data = json.dumps([asdict(a) for a in macro.actions])

        cursor.execute('''
            INSERT OR REPLACE INTO macros
            (name, device_width, device_height, created_at, description, gesture_name, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (macro.name, macro.device_width, macro.device_height,
              macro.created_at, macro.description, macro.gesture_name, data))
        self.conn.commit()

    def load_macros(self) -> List[Macro]:
        """Load all macros from the database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM macros')

        macros = []
        for row in cursor.fetchall():
            try:
                actions_data = json.loads(row[7])
                actions = []
                for a_data in actions_data:
                    # Ensure backward compatibility
                    if 'delay_before' not in a_data:
                        a_data['delay_before'] = 0.0
                    if 'slot' not in a_data:
                        a_data['slot'] = 0
                    if 'secondary_fingers' not in a_data:
                        a_data['secondary_fingers'] = []
                    if 'humanize' not in a_data:
                        a_data['humanize'] = False
                    actions.append(TouchAction(**a_data))

                macro = Macro(
                    name=row[1],
                    actions=actions,
                    device_width=row[2],
                    device_height=row[3],
                    created_at=row[4],
                    description=row[5] or "",
                    gesture_name=row[6] or ""
                )
                macros.append(macro)
            except Exception as e:
                print(f"Error loading macro {row[1]}: {e}")

        return macros

    def delete_macro(self, name: str):
        """Delete a macro from the database"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM macros WHERE name = ?', (name,))
        self.conn.commit()

    def save_profile(self, profile: Profile):
        """Save a profile to the database"""
        cursor = self.conn.cursor()
        macros_json = json.dumps(profile.macros)

        cursor.execute('''
            INSERT OR REPLACE INTO profiles
            (name, device_id, screen_width, screen_height, touch_device, macros, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (profile.name, profile.device_id, profile.screen_width,
              profile.screen_height, profile.touch_device, macros_json, profile.created_at))
        self.conn.commit()

    def load_profiles(self) -> List[Profile]:
        """Load all profiles from the database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM profiles')

        profiles = []
        for row in cursor.fetchall():
            try:
                profile = Profile(
                    name=row[1],
                    device_id=row[2],
                    screen_width=row[3],
                    screen_height=row[4],
                    touch_device=row[5],
                    macros=json.loads(row[6]),
                    created_at=row[7]
                )
                profiles.append(profile)
            except Exception as e:
                print(f"Error loading profile {row[1]}: {e}")

        return profiles

    def delete_profile(self, name: str):
        """Delete a profile from the database"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM profiles WHERE name = ?', (name,))
        self.conn.commit()

    def update_analytics(self, macro_name: str, duration: float):
        """Update analytics for a macro playback"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO analytics
            (macro_name, play_count, total_duration, last_played)
            VALUES (
                ?,
                COALESCE((SELECT play_count FROM analytics WHERE macro_name = ?), 0) + 1,
                COALESCE((SELECT total_duration FROM analytics WHERE macro_name = ?), 0) + ?,
                ?
            )
        ''', (macro_name, macro_name, macro_name, duration, datetime.now().isoformat()))
        self.conn.commit()

    def get_analytics(self) -> List[Dict]:
        """Get analytics for all macros"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM analytics')

        analytics = []
        for row in cursor.fetchall():
            analytics.append({
                'macro_name': row[1],
                'play_count': row[2],
                'total_duration': row[3],
                'avg_delay': row[4] or 0,
                'last_played': row[5]
            })

        return analytics

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            print("Database connection closed")

# ============================================================================
# PLUGIN SYSTEM
# ============================================================================

class PluginManager:
    """Manages plugins for extending functionality"""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(exist_ok=True)
        self.plugins: Dict[str, Callable] = {}
        self._load_plugins()

    def _load_plugins(self):
        """Load all plugins from the plugins directory"""
        for plugin_file in self.plugins_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for process_action function
                if hasattr(module, 'process_action'):
                    self.plugins[plugin_file.stem] = module.process_action
                    print(f"✓ Loaded plugin: {plugin_file.stem}")
            except Exception as e:
                print(f"✗ Failed to load plugin {plugin_file}: {e}")

    def process_action(self, action: TouchAction) -> TouchAction:
        """Process an action through all loaded plugins"""
        for plugin_name, plugin_func in self.plugins.items():
            try:
                action = plugin_func(action)
            except Exception as e:
                print(f"Plugin {plugin_name} error: {e}")
        return action

# ============================================================================
# UNIVERSAL EVENT PARSER
# ============================================================================

class UniversalEventParser:
    """Parses touch events from ALL Android device formats"""

    def __init__(self):
        self.slots = {i: {'x': 0, 'y': 0, 'tracking_id': -1, 'active': False}
                     for i in range(10)}
        self.current_slot = 0
        self.max_x = 1080
        self.max_y = 2400

    def parse_line(self, line: str) -> List[TouchEvent]:
        """Parse a single line from getevent output"""
        timestamp_match = re.search(r'\[\s*(\d+\.\d+)\]', line)
        if not timestamp_match:
            return []
        timestamp = float(timestamp_match.group(1))

        events = []

        # ABS_MT_SLOT - Set current slot
        if 'ABS_MT_SLOT' in line or re.search(r'\s002f\s', line):
            match = re.search(r'(?:ABS_MT_SLOT\s+|002f\s+)([0-9a-fA-F]+)', line)
            if match:
                self.current_slot = int(match.group(1), 16)
            return []

        # ABS_MT_POSITION_X - X coordinate
        if 'ABS_MT_POSITION_X' in line or re.search(r'\s0035\s', line):
            match = re.search(r'(?:ABS_MT_POSITION_X\s+|0035\s+)([0-9a-fA-F]+)', line)
            if match:
                self.slots[self.current_slot]['x'] = int(match.group(1), 16)
            return []

        # ABS_MT_POSITION_Y - Y coordinate
        if 'ABS_MT_POSITION_Y' in line or re.search(r'\s0036\s', line):
            match = re.search(r'(?:ABS_MT_POSITION_Y\s+|0036\s+)([0-9a-fA-F]+)', line)
            if match:
                self.slots[self.current_slot]['y'] = int(match.group(1), 16)
            return []

        # ABS_MT_TRACKING_ID - Touch down/up
        if 'ABS_MT_TRACKING_ID' in line or re.search(r'\s0039\s', line):
            match = re.search(r'(?:ABS_MT_TRACKING_ID\s+|0039\s+)([0-9a-fA-F]+)', line)
            if match:
                value = int(match.group(1), 16)
                if value == 0xFFFFFFFF or value > 65000:
                    value = -1

                slot_data = self.slots[self.current_slot]
                old_id = slot_data['tracking_id']
                slot_data['tracking_id'] = value

                if value == -1 and old_id >= 0:
                    slot_data['active'] = False
                    events.append(TouchEvent(timestamp, slot_data['x'], slot_data['y'], 'UP', self.current_slot))
                elif value >= 0:
                    slot_data['active'] = True
                    events.append(TouchEvent(timestamp, slot_data['x'], slot_data['y'], 'DOWN', self.current_slot))
            return events

        # BTN_TOUCH - Single-touch devices
        if 'BTN_TOUCH' in line or re.search(r'014a', line):
            slot_data = self.slots[0]
            if 'DOWN' in line or re.search(r'\s00000001$', line):
                slot_data['active'] = True
                events.append(TouchEvent(timestamp, slot_data['x'], slot_data['y'], 'DOWN', 0))
            elif 'UP' in line or re.search(r'\s00000000$', line):
                slot_data['active'] = False
                events.append(TouchEvent(timestamp, slot_data['x'], slot_data['y'], 'UP', 0))
            return events

        # SYN_REPORT - Report all active touches
        if 'SYN_REPORT' in line or re.search(r'0000\s+0000\s+00000000', line):
            for slot_id, slot_data in self.slots.items():
                if slot_data['active'] and slot_data['tracking_id'] >= 0:
                    events.append(TouchEvent(timestamp, slot_data['x'], slot_data['y'], 'MOVE', slot_id))
            return events

        return []

# ============================================================================
# TOUCH ANALYZER
# ============================================================================

class TouchAnalyzer:
    """Analyzes touch events and identifies gestures"""

    TAP_DURATION_MAX = 0.3
    HOLD_DURATION_MIN = 0.5
    TAP_MOVEMENT_MAX = 30

    def __init__(self):
        self.active_fingers: Dict[int, dict] = {}
        self.last_action_timestamp = 0.0

    def process_event(self, event: TouchEvent) -> Optional[TouchAction]:
        """Process a touch event and return a complete action if applicable"""
        slot = event.slot

        if event.event_type == 'DOWN':
            self.active_fingers[slot] = {
                'down_event': event,
                'move_events': [],
                'start_time': event.timestamp
            }
            return None

        elif event.event_type == 'MOVE':
            if slot in self.active_fingers:
                self.active_fingers[slot]['move_events'].append(event)
            return None

        elif event.event_type == 'UP':
            if slot not in self.active_fingers:
                return None

            finger_data = self.active_fingers[slot]
            action = self._analyze_gesture(finger_data, event)

            # Calculate delay from previous action
            if self.last_action_timestamp > 0:
                action.delay_before = action.timestamp - self.last_action_timestamp
            else:
                action.delay_before = 0.0

            self.last_action_timestamp = action.timestamp

            # Check for multi-touch
            action.secondary_fingers = []
            for other_slot, other_data in self.active_fingers.items():
                if other_slot != slot and 'down_event' in other_data:
                    other_event = other_data['down_event']
                    action.secondary_fingers.append((other_event.x, other_event.y))

            if action.secondary_fingers:
                action.action_type = 'MULTI_TAP'

            del self.active_fingers[slot]
            return action

        return None

    def _analyze_gesture(self, finger_data: dict, up_event: TouchEvent) -> TouchAction:
        """Analyze the gesture type based on movement and duration"""
        down_event = finger_data['down_event']
        duration = up_event.timestamp - down_event.timestamp

        dx = up_event.x - down_event.x
        dy = up_event.y - down_event.y
        distance = math.sqrt(dx**2 + dy**2)

        if duration >= self.HOLD_DURATION_MIN and distance < self.TAP_MOVEMENT_MAX:
            return TouchAction('HOLD', down_event.x, down_event.y,
                             duration=duration, timestamp=down_event.timestamp, slot=down_event.slot)
        elif duration < self.TAP_DURATION_MAX and distance < self.TAP_MOVEMENT_MAX:
            return TouchAction('TAP', down_event.x, down_event.y,
                             duration=duration, timestamp=down_event.timestamp, slot=down_event.slot)
        else:
            return TouchAction('SWIPE', down_event.x, down_event.y, up_event.x, up_event.y,
                             duration=duration, timestamp=down_event.timestamp, slot=down_event.slot)

# ============================================================================
# ADB INTERFACE
# ============================================================================

class ADBInterface:
    """Interface for communicating with Android devices via ADB"""

    def __init__(self, device_cache: DeviceCache):
        self.device_id: Optional[str] = None
        self.screen_width = 1080
        self.screen_height = 2400
        self.touch_device: Optional[str] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.is_connected = False
        self.reconnect_attempts = 0
        self.device_cache = device_cache

    def check_adb(self) -> bool:
        """Check if ADB is available"""
        try:
            result = subprocess.run(['adb', 'version'], capture_output=True, check=True, text=True, timeout=5)
            return True
        except:
            return False

    def get_devices(self) -> List[str]:
        """Get list of connected devices"""
        try:
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split('\n')[1:]
        
        # Match both tabs AND spaces before "device"
            devices = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == 'device':
                    devices.append(parts[0])
        
            return devices
        except Exception as e:
            print(f"get_devices error: {e}")
            return []

    def get_device_fingerprint(self) -> Optional[str]:
        """Get unique device identifier (serial number)"""
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'getprop', 'ro.serialno'])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            serial = result.stdout.strip()
            
            if serial and serial != "unknown":
                return serial
            
            # Fallback to device ID if serial unavailable
            return self.device_id
        except Exception as e:
            print(f"Could not get device fingerprint: {e}")
            return self.device_id

    def detect_touch_device_smart(self) -> Optional[str]:
        """
        Smart auto-detection using getevent -il
        Looks for multitouch capabilities and caches results
        """
        # First, check cache
        fingerprint = self.get_device_fingerprint()
        if fingerprint:
            cached_device = self.device_cache.get(fingerprint)
            if cached_device:
                print(f"🎯 Using cached touch device: {cached_device}")
                # Verify it still exists
                if self._verify_device_exists(cached_device):
                    return cached_device
                else:
                    print(f"⚠️ Cached device {cached_device} no longer exists, rescanning...")
                    self.device_cache.remove(fingerprint)
        
        # No cache or cache invalid, perform smart detection
        print("🔍 Auto-detecting touch device using getevent -il...")
        touch_device = self._scan_for_multitouch_device()
        
        if touch_device and fingerprint:
            # Cache the result
            self.device_cache.set(fingerprint, touch_device)
            return touch_device
        
        return touch_device

    def _verify_device_exists(self, device_path: str) -> bool:
        """Verify that a device path still exists on the phone"""
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'ls', device_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            return result.returncode == 0 and device_path in result.stdout
        except:
            return False

    def _scan_for_multitouch_device(self) -> Optional[str]:
        """
        Scan all input devices for multitouch capabilities
        Uses getevent -il to get detailed device info
        """
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'getevent', '-il'])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            # Parse the output
            devices = self._parse_getevent_il(result.stdout)
            
            # Filter for devices with multitouch capabilities
            multitouch_devices = []
            for device_path, capabilities in devices.items():
                has_mt_x = 'ABS_MT_POSITION_X' in capabilities
                has_mt_y = 'ABS_MT_POSITION_Y' in capabilities
                has_tracking = 'ABS_MT_TRACKING_ID' in capabilities
                
                if has_mt_x and has_mt_y:
                    # This is a multitouch device
                    multitouch_devices.append(device_path)
                    print(f"✓ Found multitouch device: {device_path}")
            
            if multitouch_devices:
                # Return the first multitouch device found
                return multitouch_devices[0]
            
            # Fallback: look for any touch device (single touch)
            print("⚠️ No multitouch device found, looking for single-touch...")
            for device_path, capabilities in devices.items():
                has_abs_x = 'ABS_X' in capabilities
                has_abs_y = 'ABS_Y' in capabilities
                has_btn_touch = 'BTN_TOUCH' in capabilities
                
                if (has_abs_x and has_abs_y) or has_btn_touch:
                    print(f"✓ Found single-touch device: {device_path}")
                    return device_path
            
            return None
            
        except Exception as e:
            print(f"Error during smart detection: {e}")
            return None

    def _parse_getevent_il(self, output: str) -> Dict[str, List[str]]:
        """
        Parse getevent -il output to extract device capabilities
        Returns: {device_path: [list of capabilities]}
        """
        devices = {}
        current_device = None
        current_capabilities = []
        
        for line in output.split('\n'):
            # Device line: "add device 4: /dev/input/event4"
            if 'add device' in line:
                # Save previous device
                if current_device:
                    devices[current_device] = current_capabilities
                
                # Extract new device path
                match = re.search(r'add device \d+: (/dev/input/event\d+)', line)
                if match:
                    current_device = match.group(1)
                    current_capabilities = []
            
            # Capability lines contain ABS_MT_POSITION_X, etc.
            elif current_device:
                # Look for key capability indicators
                if 'ABS_MT_POSITION_X' in line:
                    current_capabilities.append('ABS_MT_POSITION_X')
                elif 'ABS_MT_POSITION_Y' in line:
                    current_capabilities.append('ABS_MT_POSITION_Y')
                elif 'ABS_MT_TRACKING_ID' in line:
                    current_capabilities.append('ABS_MT_TRACKING_ID')
                elif 'ABS_X' in line and 'ABS_MT' not in line:
                    current_capabilities.append('ABS_X')
                elif 'ABS_Y' in line and 'ABS_MT' not in line:
                    current_capabilities.append('ABS_Y')
                elif 'BTN_TOUCH' in line:
                    current_capabilities.append('BTN_TOUCH')
        
        # Save last device
        if current_device:
            devices[current_device] = current_capabilities
        
        return devices

    def list_all_input_devices(self) -> List[Tuple[str, str, bool]]:
        """List all input devices with touch detection"""
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'getevent', '-p'])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            devices = []
            current_device = None
            current_caps = []
            has_touch = False

            for line in result.stdout.split('\n'):
                if 'add device' in line:
                    if current_device:
                        cap_str = ' | '.join(current_caps[:3]) if current_caps else 'Unknown'
                        devices.append((current_device, cap_str, has_touch))

                    match = re.search(r'add device \d+: (/dev/input/event\d+)', line)
                    if match:
                        current_device = match.group(1)
                        current_caps = []
                        has_touch = False

                if current_device:
                    if any(kw in line for kw in ['ABS_MT_POSITION', 'ABS_X', 'ABS_Y', 'BTN_TOUCH']):
                        has_touch = True
                        if 'ABS_MT' in line:
                            current_caps.append('MultiTouch')
                        elif 'ABS_X' in line or 'ABS_Y' in line:
                            current_caps.append('SingleTouch')

            if current_device:
                cap_str = ' | '.join(current_caps[:3]) if current_caps else 'Unknown'
                devices.append((current_device, cap_str, has_touch))

            return devices
        except Exception as e:
            print(f"List devices error: {e}")
            return []

    def detect_touch_device(self) -> Optional[str]:
        """
        Legacy method - redirects to smart detection
        Kept for backward compatibility
        """
        return self.detect_touch_device_smart()

    def _quick_test(self, device: str) -> bool:
        """Quick test if device supports touch"""
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'getevent', '-p', device])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            return any(kw in result.stdout for kw in ['ABS_MT', 'ABS_X', 'BTN_TOUCH'])
        except:
            return False

    def get_screen_size(self) -> Tuple[int, int]:
        """Get device screen resolution"""
        try:
            cmd = ['adb']
            if self.device_id:
                cmd.extend(['-s', self.device_id])
            cmd.extend(['shell', 'wm', 'size'])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                self.screen_width = int(match.group(1))
                self.screen_height = int(match.group(2))
        except:
            pass
        return self.screen_width, self.screen_height

    def start_event_stream(self, event_queue: queue.Queue, device: str):
        """Start streaming touch events from device"""
        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        cmd.extend(['shell', 'getevent', '-lt', device])

        def reader():
            while True:
                try:
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True, bufsize=1)
                    event_queue.put(('INFO', f'Streaming from {device}'))
                    self.is_connected = True
                    self.reconnect_attempts = 0

                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            event_queue.put(('EVENT', line))

                except Exception as e:
                    self.is_connected = False
                    event_queue.put(('ERROR', f'Stream error: {str(e)}'))
                    self.reconnect_attempts += 1

                    if self.reconnect_attempts < 3:
                        event_queue.put(('WARNING', f'Reconnecting... (attempt {self.reconnect_attempts})'))
                        time.sleep(2)
                    else:
                        event_queue.put(('ERROR', 'Max reconnect attempts reached'))
                        break

        self.executor.submit(reader)

    def execute_tap(self, x: int, y: int, humanize: bool = False):
        """Execute a tap action on the device"""
        if humanize:
            x += random.randint(-5, 5)
            y += random.randint(-5, 5)
            time.sleep(random.uniform(0.01, 0.05))

        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        cmd.extend(['shell', 'input', 'tap', str(x), str(y)])
        self.executor.submit(subprocess.run, cmd, capture_output=True)

    def execute_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, humanize: bool = False):
        """Execute a swipe action on the device"""
        if humanize:
            x2 += random.randint(-3, 3)
            y2 += random.randint(-3, 3)
            duration_ms += random.randint(-20, 20)

        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        cmd.extend(['shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
        self.executor.submit(subprocess.run, cmd, capture_output=True)

    def execute_hold(self, x: int, y: int, duration: float, humanize: bool = False):
        """Execute a hold action on the device"""
        duration_ms = int(duration * 1000)
        if humanize:
            duration_ms += random.randint(-50, 50)

        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        cmd.extend(['shell', 'input', 'swipe', str(x), str(y), str(x), str(y), str(duration_ms)])
        self.executor.submit(subprocess.run, cmd, capture_output=True)

    def execute_multi_tap(self, positions: List[Tuple[int, int]], humanize: bool = False):
        """Execute multiple taps simultaneously"""
        for x, y in positions:
            self.execute_tap(x, y, humanize)
            time.sleep(0.01)

# ============================================================================
# VISUAL GESTURE MAP CANVAS
# ============================================================================

class GestureMapCanvas(tk.Canvas):
    """Visual representation of touch gestures"""

    FINGER_COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
                     '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#ABEBC6']

    def __init__(self, parent, width=400, height=700):
        super().__init__(parent, width=width, height=height, bg='#1e1e1e', highlightthickness=0)
        self.width = width
        self.height = height
        self.device_width = 1080
        self.device_height = 2400
        self.touches = {}  # slot_id: (x, y, color)
        self.trails = []  # List of (x1, y1, x2, y2, color) for swipe trails
        self.max_trails = 20

    def set_device_size(self, width: int, height: int):
        """Set the device screen dimensions"""
        self.device_width = width
        self.device_height = height

    def scale_coords(self, x: int, y: int) -> Tuple[int, int]:
        """Scale device coordinates to canvas coordinates"""
        canvas_x = int((x / self.device_width) * self.width)
        canvas_y = int((y / self.device_height) * self.height)
        return canvas_x, canvas_y

    def add_touch(self, slot: int, x: int, y: int, event_type: str):
        """Add a touch event to the visual map"""
        cx, cy = self.scale_coords(x, y)
        color = self.FINGER_COLORS[slot % len(self.FINGER_COLORS)]

        if event_type == 'DOWN':
            self.touches[slot] = (cx, cy, color)
        elif event_type == 'MOVE' and slot in self.touches:
            old_cx, old_cy, _ = self.touches[slot]
            self.trails.append((old_cx, old_cy, cx, cy, color))
            if len(self.trails) > self.max_trails:
                self.trails.pop(0)
            self.touches[slot] = (cx, cy, color)
        elif event_type == 'UP' and slot in self.touches:
            del self.touches[slot]

        self.redraw()

    def redraw(self):
        """Redraw the gesture map"""
        self.delete('all')

        # Draw grid
        for i in range(0, self.width, 50):
            self.create_line(i, 0, i, self.height, fill='#3e3e3e', dash=(2, 4))
        for i in range(0, self.height, 50):
            self.create_line(0, i, self.width, i, fill='#3e3e3e', dash=(2, 4))

        # Draw trails
        for x1, y1, x2, y2, color in self.trails:
            self.create_line(x1, y1, x2, y2, fill=color, width=2, arrow=tk.LAST)

        # Draw active touches
        for slot, (cx, cy, color) in self.touches.items():
            self.create_oval(cx-15, cy-15, cx+15, cy+15, fill=color, outline='white', width=2)
            self.create_text(cx, cy, text=str(slot), fill='white', font=('Arial', 12, 'bold'))

    def clear(self):
        """Clear the gesture map"""
        self.touches.clear()
        self.trails.clear()
        self.redraw()

# ============================================================================
# MACRO TIMELINE EDITOR
# ============================================================================

class MacroTimelineEditor(tk.Toplevel):
    """Visual timeline editor for macros"""

    def __init__(self, parent, macro: Macro, callback):
        super().__init__(parent)
        self.title(f"Edit Macro: {macro.name}")
        self.geometry("900x600")
        self.macro = macro
        self.callback = callback

        # Timeline canvas
        self.canvas = tk.Canvas(self, bg='#2d2d2d', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Controls
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(controls, text="💾 Save", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="🗑️ Delete Selected", command=self._delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="⏱️ Add Delay", command=self._add_delay).pack(side=tk.LEFT, padx=5)

        self.info_label = ttk.Label(controls, text="Click actions to select | Drag to reorder")
        self.info_label.pack(side=tk.LEFT, padx=15)

        self.selected_index = None
        self._draw_timeline()

        self.canvas.bind('<Button-1>', self._on_click)

    def _draw_timeline(self):
        """Draw the timeline visualization"""
        self.canvas.delete('all')

        if not self.macro.actions:
            self.canvas.create_text(450, 300, text="No actions in this macro",
                                   fill='white', font=('Arial', 14))
            return

        y = 50
        total_time = sum(a.delay_before + a.duration for a in self.macro.actions)
        scale = 750 / max(total_time, 1)  # pixels per second

        current_time = 0
        for i, action in enumerate(self.macro.actions):
            x_start = 75 + current_time * scale

            # Draw delay bar
            if action.delay_before > 0:
                delay_width = action.delay_before * scale
                self.canvas.create_rectangle(x_start, y, x_start + delay_width, y + 40,
                                            fill='#555', outline='white', tags=f'delay_{i}')
                self.canvas.create_text(x_start + delay_width / 2, y + 20,
                                       text=f"{int(action.delay_before*1000)}ms", fill='white', font=('Arial', 8))
                x_start += delay_width
                current_time += action.delay_before

            # Draw action bar
            action_width = max(action.duration * scale, 40)
            color = {
                'TAP': '#4ECDC4',
                'HOLD': '#FFA07A',
                'SWIPE': '#45B7D1',
                'MULTI_TAP': '#F7DC6F'
            }.get(action.action_type, '#aaa')

            is_selected = (i == self.selected_index)
            width = 4 if is_selected else 2

            self.canvas.create_rectangle(x_start, y, x_start + action_width, y + 40,
                                        fill=color, outline='white' if not is_selected else 'yellow',
                                        width=width, tags=f'action_{i}')
            self.canvas.create_text(x_start + action_width / 2, y + 20,
                                   text=action.action_type, fill='black', font=('Arial', 10, 'bold'))

            # Draw action info
            info = f"#{i+1}: ({action.start_x}, {action.start_y})"
            if action.end_x is not None:
                info += f" → ({action.end_x}, {action.end_y})"
            self.canvas.create_text(x_start + action_width / 2, y + 55,
                                   text=info, fill='white', font=('Arial', 7))

            current_time += action.duration
            y += 80

    def _on_click(self, event):
        """Handle click on timeline"""
        items = self.canvas.find_overlapping(event.x - 5, event.y - 5, event.x + 5, event.y + 5)
        for item in items:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith('action_'):
                    self.selected_index = int(tag.split('_')[1])
                    self._draw_timeline()
                    return

    def _delete_selected(self):
        """Delete the selected action"""
        if self.selected_index is not None and self.selected_index < len(self.macro.actions):
            del self.macro.actions[self.selected_index]
            self.selected_index = None
            self._draw_timeline()

    def _add_delay(self):
        """Add delay to selected action"""
        if self.selected_index is not None and self.selected_index < len(self.macro.actions):
            delay = simpledialog.askfloat("Add Delay", "Enter delay in seconds:",
                                         minvalue=0, maxvalue=10, parent=self)
            if delay is not None:
                self.macro.actions[self.selected_index].delay_before = delay
                self._draw_timeline()

    def _save(self):
        """Save the edited macro"""
        self.callback(self.macro)
        messagebox.showinfo("Saved", f"Macro '{self.macro.name}' updated!", parent=self)
        self.destroy()

# ============================================================================
# ANALYTICS CHARTS
# ============================================================================

class AnalyticsWindow(tk.Toplevel):
    """Analytics dashboard for macro usage statistics"""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent)
        self.title("Analytics Dashboard")
        self.geometry("800x600")
        self.db = db

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Overview tab
        overview = ttk.Frame(notebook)
        notebook.add(overview, text="📊 Overview")
        self._build_overview(overview)

        # Charts tab
        charts = ttk.Frame(notebook)
        notebook.add(charts, text="📈 Charts")
        self._build_charts(charts)

    def _build_overview(self, parent):
        """Build overview statistics"""
        analytics = self.db.get_analytics()

        if not analytics:
            ttk.Label(parent, text="No analytics data yet!", font=('Arial', 14)).pack(pady=50)
            return

        # Summary stats
        stats_frame = ttk.LabelFrame(parent, text="Summary Statistics", padding=20)
        stats_frame.pack(fill=tk.X, padx=20, pady=20)

        total_plays = sum(a['play_count'] for a in analytics)
        total_duration = sum(a['total_duration'] for a in analytics)
        most_played = max(analytics, key=lambda x: x['play_count'])

        ttk.Label(stats_frame, text=f"Total Macros Played: {total_plays}",
                 font=('Arial', 12)).pack(anchor='w', pady=5)
        ttk.Label(stats_frame, text=f"Total Duration: {total_duration:.1f}s",
                 font=('Arial', 12)).pack(anchor='w', pady=5)
        ttk.Label(stats_frame, text=f"Most Played: {most_played['macro_name']} ({most_played['play_count']} times)",
                 font=('Arial', 12)).pack(anchor='w', pady=5)

        # List all macros
        list_frame = ttk.LabelFrame(parent, text="Macro Statistics", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Consolas', 10))
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for a in sorted(analytics, key=lambda x: x['play_count'], reverse=True):
            text = f"{a['macro_name']:25s}  Plays: {a['play_count']:3d}  Duration: {a['total_duration']:.1f}s"
            listbox.insert(tk.END, text)

    def _build_charts(self, parent):
        """Build visual charts"""
        analytics = self.db.get_analytics()

        if not analytics:
            ttk.Label(parent, text="No data to chart!", font=('Arial', 14)).pack(pady=50)
            return

        canvas = tk.Canvas(parent, bg='#2d2d2d', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Draw bar chart for play counts
        sorted_data = sorted(analytics, key=lambda x: x['play_count'], reverse=True)[:10]
        if not sorted_data:
            return

        max_count = max(a['play_count'] for a in sorted_data)

        y = 50
        for i, a in enumerate(sorted_data):
            bar_width = (a['play_count'] / max_count) * 600 if max_count > 0 else 0
            canvas.create_rectangle(150, y, 150 + bar_width, y + 30, fill='#4ECDC4', outline='white')
            canvas.create_text(140, y + 15, text=a['macro_name'][:15], fill='white', anchor='e', font=('Arial', 9))
            canvas.create_text(160 + bar_width, y + 15, text=str(a['play_count']),
                             fill='white', anchor='w', font=('Arial', 9, 'bold'))
            y += 45

# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class TouchLoggerGUI:
    """Main GUI application"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Touch Logger v{VERSION}")
        self.root.geometry("1400x900")

        # Initialize systems
        self.theme = ThemeManager()
        self.db = DatabaseManager(Path("touch_logger.db"))
        self.device_cache = DeviceCache()  # NEW: Device cache
        self.plugins = PluginManager(Path("plugins"))
        self.adb = ADBInterface(self.device_cache)  # Pass cache to ADB
        self.parser = UniversalEventParser()
        self.analyzer = TouchAnalyzer()

        # State
        self.event_queue = queue.Queue()
        self.is_recording = False
        self.recorded_actions: List[TouchAction] = []
        self.macros: List[Macro] = []
        self.profiles: List[Profile] = []
        self.event_count = 0
        self.is_playing = False
        self.current_profile: Optional[Profile] = None

        # Storage
        self.log_file = Path("log.txt")
        if self.log_file.exists():
            self.log_file.write_text(f"=== Session: {datetime.now().isoformat()} ===\n")

        # Performance
        self.last_ui_update = time.time()
        self.event_rate = 0
        self.recording_start_time = 0

        # Build UI
        self._build_ui()
        self._setup_hotkeys()
        self._apply_theme()
        self._check_adb()
        self._load_data()
        self._start_event_processor()
        self._start_status_updater()

        # Register cleanup handler for proper shutdown
        self.root.protocol("WM_DELETE_WINDOW", self._cleanup)

    def _build_ui(self):
        """Build the user interface"""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left panel - Controls and lists
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=3)

        # Top toolbar with status
        self._build_toolbar(left_panel)

        # Notebook
        self.notebook = ttk.Notebook(left_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tabs
        self._build_record_tab()
        self._build_playback_tab()
        self._build_profiles_tab()
        self._build_log_tab()

        # Right panel - Visual gesture map
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)
        self._build_gesture_map(right_panel)

    def _build_toolbar(self, parent):
        """Build the toolbar"""
        toolbar = ttk.Frame(parent, padding=10)
        toolbar.pack(fill=tk.X)

        # Device controls
        ttk.Label(toolbar, text="Device:").pack(side=tk.LEFT, padx=5)

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(toolbar, textvariable=self.device_var,
                                         width=20, state='readonly')
        self.device_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="↻", command=self._refresh_devices, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Connect", command=self._connect_device).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔍", command=self._show_device_selector, width=3).pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(toolbar, text="●", foreground="red", font=('Arial', 14))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Cache status indicator
        self.cache_label = ttk.Label(toolbar, text="💾", foreground="gray", font=('Arial', 12))
        self.cache_label.pack(side=tk.LEFT, padx=5)

        # Right side controls
        ttk.Button(toolbar, text="📊 Analytics", command=self._show_analytics).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="🌙", command=self._toggle_theme, width=3).pack(side=tk.RIGHT, padx=2)

        # Status bar
        status_bar = ttk.Frame(parent, padding=5)
        status_bar.pack(fill=tk.X)

        self.event_rate_label = ttk.Label(status_bar, text="Events/s: 0")
        self.event_rate_label.pack(side=tk.LEFT, padx=10)

        self.recording_time_label = ttk.Label(status_bar, text="Recording: 00:00")
        self.recording_time_label.pack(side=tk.LEFT, padx=10)

        self.connection_status_label = ttk.Label(status_bar, text="Disconnected", foreground="red")
        self.connection_status_label.pack(side=tk.LEFT, padx=10)

        self.profile_label = ttk.Label(status_bar, text="Profile: None")
        self.profile_label.pack(side=tk.RIGHT, padx=10)

    def _build_record_tab(self):
        """Build the recording tab"""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="🔹 Record")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=10)

        self.record_btn = ttk.Button(controls, text="🔴 Record (F9)", command=self._toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls, text="Clear", command=self._clear_recording).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="💾 Save", command=self._save_macro).pack(side=tk.LEFT, padx=5)

        self.humanize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="🎭 Humanize (random jitter)",
                       variable=self.humanize_var).pack(side=tk.LEFT, padx=15)

        self.action_count_label = ttk.Label(controls, text="Actions: 0")
        self.action_count_label.pack(side=tk.RIGHT, padx=5)

        # Actions list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.actions_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Consolas', 9))
        self.actions_list.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.actions_list.yview)

    def _build_playback_tab(self):
        """Build the playback tab"""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="▶️ Playback")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=10)

        ttk.Label(controls, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(controls, from_=0.1, to=5.0, increment=0.1,
                   textvariable=self.speed_var, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Label(controls, text="Loop:").pack(side=tk.LEFT, padx=10)
        self.loop_var = tk.IntVar(value=1)
        ttk.Spinbox(controls, from_=1, to=999, textvariable=self.loop_var, width=6).pack(side=tk.LEFT, padx=5)

        self.scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Scale", variable=self.scale_var).pack(side=tk.LEFT, padx=10)

        self.play_btn = ttk.Button(controls, text="▶️ Play (F11)", command=self._toggle_playback)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls, text="✏️ Edit", command=self._edit_macro).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="📤 Export", command=self._export_macro).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="📥 Import", command=self._import_macro).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="🗑️", command=self._delete_macro).pack(side=tk.LEFT, padx=5)

        self.playback_status = ttk.Label(controls, text="", foreground="blue")
        self.playback_status.pack(side=tk.RIGHT, padx=5)

        # Macros list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.macros_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Consolas', 9))
        self.macros_list.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.macros_list.yview)
        self.macros_list.bind('<<ListboxSelect>>', self._on_macro_select)

        # Details
        detail_frame = ttk.LabelFrame(frame, text="Details", padding=10)
        detail_frame.pack(fill=tk.X, pady=10)

        self.macro_detail = tk.Text(detail_frame, height=6, font=('Consolas', 8))
        self.macro_detail.pack(fill=tk.BOTH, expand=True)

    def _build_profiles_tab(self):
        """Build the profiles tab"""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="👤 Profiles")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=10)

        ttk.Button(controls, text="💾 Save Current", command=self._save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Load Selected", command=self._load_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="🗑️ Delete", command=self._delete_profile).pack(side=tk.LEFT, padx=5)

        # Profiles list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.profiles_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Consolas', 10))
        self.profiles_list.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.profiles_list.yview)

    def _build_log_tab(self):
        """Build the log tab"""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="📋 Log")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=10)

        ttk.Button(controls, text="Clear", command=self._clear_log).pack(side=tk.LEFT, padx=5)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Auto-scroll", variable=self.auto_scroll_var).pack(side=tk.LEFT, padx=15)

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_frame, yscrollcommand=scrollbar.set, font=('Consolas', 8), wrap=tk.NONE)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

    def _build_gesture_map(self, parent):
        """Build the gesture visualization"""
        ttk.Label(parent, text="Visual Gesture Map", font=('Arial', 12, 'bold')).pack(pady=10)

        self.gesture_canvas = GestureMapCanvas(parent, width=350, height=600)
        self.gesture_canvas.pack(padx=10, pady=10)

        controls = ttk.Frame(parent)
        controls.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(controls, text="Clear Map", command=lambda: self.gesture_canvas.clear()).pack(fill=tk.X)

    def _setup_hotkeys(self):
        """Setup keyboard hotkeys"""
        self.root.bind(HOTKEYS['record'], lambda e: self._toggle_recording())
        self.root.bind(HOTKEYS['stop'], lambda e: self._toggle_recording() if self.is_recording else None)
        self.root.bind(HOTKEYS['play'], lambda e: self._toggle_playback())
        self.root.bind(HOTKEYS['theme'], lambda e: self._toggle_theme())

    def _apply_theme(self):
        """Apply the current theme"""
        try:
            self.root.configure(bg=self.theme.current['bg'])

            for widget in [self.log_text, self.macro_detail]:
                widget.config(bg=self.theme.current['text_bg'],
                            fg=self.theme.current['text_fg'],
                            insertbackground=self.theme.current['text_fg'])

            for listbox in [self.actions_list, self.macros_list, self.profiles_list]:
                listbox.config(bg=self.theme.current['text_bg'],
                             fg=self.theme.current['text_fg'],
                             selectbackground=self.theme.current['select_bg'])

            self.gesture_canvas.config(bg=self.theme.current['chart_bg'])
        except:
            pass

    def _toggle_theme(self):
        """Toggle between dark and light themes"""
        self.theme.is_dark = not self.theme.is_dark
        self.theme.current = self.theme.DARK.copy() if self.theme.is_dark else self.theme.LIGHT.copy()
        self._apply_theme()
        mode = "Dark" if self.theme.is_dark else "Light"
        self._log(f"🎨 Switched to {mode} mode")

    def _show_device_selector(self):
        """Show manual device selector dialog"""
        if not self.adb.device_id:
            messagebox.showwarning("No Device", "Connect to a device first")
            return

        selector = tk.Toplevel(self.root)
        selector.title("Select Touch Device")
        selector.geometry("750x450")
        selector.transient(self.root)

        ttk.Label(selector, text="Select the touch input device:",
                 font=('Arial', 11, 'bold')).pack(pady=10)

        frame = ttk.Frame(selector)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=('Consolas', 9))
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        self._log("🔍 Scanning input devices...")
        devices = self.adb.list_all_input_devices()

        if not devices:
            listbox.insert(tk.END, "No devices found! Check ADB connection.")
            return

        device_list = []
        for dev, caps, is_touch in devices:
            status = "✓ TOUCH" if is_touch else "  Other"
            text = f"{status}  {dev:25s}  {caps}"
            listbox.insert(tk.END, text)
            device_list.append((dev, is_touch))

        def select():
            sel = listbox.curselection()
            if sel:
                dev, is_touch = device_list[sel[0]]
                self.adb.touch_device = dev
                
                # Cache the manually selected device
                fingerprint = self.adb.get_device_fingerprint()
                if fingerprint:
                    self.device_cache.set(fingerprint, dev)
                    self.cache_label.config(foreground="green")
                
                self.adb.start_event_stream(self.event_queue, dev)
                self._log(f"✓ Manually selected: {dev}")
                selector.destroy()
                messagebox.showinfo("Device Set", f"Touch device set to:\n{dev}")

        ttk.Button(selector, text="Select Device", command=select).pack(pady=10)

        self._log(f"Found {len(devices)} input devices ({sum(1 for _, _, t in devices if t)} touch)")

    def _check_adb(self):
        """Check if ADB is available"""
        if not self.adb.check_adb():
            messagebox.showerror("ADB Not Found",
                               "ADB not found in PATH\n\nInstall Android SDK Platform Tools")
        else:
            self._refresh_devices()

    def _refresh_devices(self):
        """Refresh the list of connected devices"""
        devices = self.adb.get_devices()
        self.device_combo['values'] = devices
        if devices:
            self.device_combo.current(0)
            self._log(f"Found {len(devices)} device(s)")

    def _connect_device(self):
        """Connect to the selected device"""
        device = self.device_var.get()
        if not device:
            messagebox.showwarning("No Device", "Select a device first")
            return

        self.adb.device_id = device
        w, h = self.adb.get_screen_size()
        self.parser.max_x = w
        self.parser.max_y = h
        self.gesture_canvas.set_device_size(w, h)

        self._log(f"🔍 Smart detection starting...")
        
        # Use smart detection (with caching)
        touch_device = self.adb.detect_touch_device_smart()

        if not touch_device:
            self._log("⚠️ Auto-detection failed. Use '🔍 Find Touch' button.")
            self.cache_label.config(foreground="red")
            messagebox.showwarning("Touch Device Not Found",
                                 "Could not auto-detect touch device.\n\n"
                                 "Click '🔍' button to select manually.")
            self.status_label.config(text="●", foreground="orange")
            return

        self.adb.touch_device = touch_device
        
        # Check if this was from cache
        fingerprint = self.adb.get_device_fingerprint()
        if fingerprint and self.device_cache.exists(fingerprint):
            self._log(f"💾 Loaded from cache!")
            self.cache_label.config(foreground="green")
        else:
            self._log(f"🔍 Detected and cached!")
            self.cache_label.config(foreground="blue")
        
        self.adb.start_event_stream(self.event_queue, touch_device)

        self.status_label.config(text="●", foreground="green")
        self._log(f"✓ Connected: {device}")
        self._log(f"✓ Screen: {w}x{h}")
        self._log(f"✓ Touch device: {touch_device}")
        self._log("👆 Touch your device screen now!")

    def _start_event_processor(self):
        """Start the event processing loop"""
        try:
            processed = 0
            while not self.event_queue.empty() and processed < 100:
                msg_type, data = self.event_queue.get_nowait()
                processed += 1

                if msg_type == 'EVENT':
                    self._process_event_line(data)
                elif msg_type == 'ERROR':
                    self._log(f"❌ {data}")
                    self.status_label.config(text="●", foreground="red")
                elif msg_type == 'WARNING':
                    self._log(f"⚠️ {data}")
                    self.status_label.config(text="●", foreground="orange")
                elif msg_type == 'INFO':
                    self._log(f"ℹ️ {data}")
        except queue.Empty:
            pass

        self.root.after(50, self._start_event_processor)

    def _start_status_updater(self):
        """Start the status update loop"""
        # Event rate
        now = time.time()
        if now - self.last_ui_update > 1:
            self.event_rate = self.event_count / max(now - self.last_ui_update, 1)
            self.event_rate_label.config(text=f"Events/s: {self.event_rate:.1f}")
            self.event_count = 0
            self.last_ui_update = now

        # Recording time
        if self.is_recording:
            elapsed = time.time() - self.recording_start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            self.recording_time_label.config(text=f"Recording: {mins:02d}:{secs:02d}")
        else:
            self.recording_time_label.config(text="Recording: 00:00")

        # Connection status
        if self.adb.is_connected:
            self.connection_status_label.config(text="Connected", foreground="green")
        else:
            self.connection_status_label.config(text="Disconnected", foreground="red")

        self.root.after(1000, self._start_status_updater)

    def _process_event_line(self, line: str):
        """Process a single event line"""
        events = self.parser.parse_line(line)

        for event in events:
            self.event_count += 1

            # Update visual map
            self.gesture_canvas.add_touch(event.slot, event.x, event.y, event.event_type)

            # Log important events
            if event.event_type in ['DOWN', 'UP']:
                self._log(f"Slot{event.slot} {event.event_type:5s} @ ({event.x:4d}, {event.y:4d})")

            # Write to file
            with open(self.log_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} {event.event_type} {event.x} {event.y}\n")

            # Analyze
            action = self.analyzer.process_event(event)
            if action:
                # Apply plugins
                action = self.plugins.process_action(action)

                # Apply humanization setting
                action.humanize = self.humanize_var.get()

                action_desc = self._format_action(action)
                self._log(f"🎯 {action_desc}")

                if self.is_recording:
                    self.recorded_actions.append(action)
                    self._update_actions_display()

    def _format_action(self, action: TouchAction) -> str:
        """Format action for display"""
        delay = f"[+{int(action.delay_before * 1000)}ms] " if action.delay_before > 0 else ""
        human = "🎭 " if action.humanize else ""

        if action.action_type == 'TAP':
            return f"{human}{delay}TAP ({action.start_x}, {action.start_y})"
        elif action.action_type == 'HOLD':
            return f"{human}{delay}HOLD ({action.start_x}, {action.start_y}) {action.duration:.2f}s"
        elif action.action_type == 'SWIPE':
            return f"{human}{delay}SWIPE ({action.start_x}, {action.start_y}) → ({action.end_x}, {action.end_y})"
        elif action.action_type == 'MULTI_TAP':
            fingers = len(action.secondary_fingers) + 1
            return f"{human}{delay}MULTI {fingers}F @ ({action.start_x}, {action.start_y})"
        return f"{human}{delay}{action.action_type}"

    def _log(self, message: str):
        """Log a message"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_msg = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, full_msg)
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)

        # Keep only last 300 lines
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 300:
            self.log_text.delete('1.0', '50.0')

    def _toggle_recording(self):
        """Toggle recording state"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.record_btn.config(text="⏹️ Stop (F10)")
            self.analyzer.last_action_timestamp = 0.0
            self.analyzer.active_fingers.clear()
            self.recording_start_time = time.time()
            self._log("🔴 Recording... Try TAP, HOLD (500ms+), SWIPE, MULTI-TOUCH!")
        else:
            self.record_btn.config(text="🔴 Record (F9)")
            self._log(f"⏹️ Stopped: {len(self.recorded_actions)} actions")

    def _clear_recording(self):
        """Clear recorded actions"""
        if self.recorded_actions and not messagebox.askyesno("Clear",
            f"Clear {len(self.recorded_actions)} actions?"):
            return
        self.recorded_actions.clear()
        self.actions_list.delete(0, tk.END)
        self.action_count_label.config(text="Actions: 0")
        self._log("🗑️ Cleared recordings")

    def _update_actions_display(self):
        """Update the actions list display"""
        self.actions_list.delete(0, tk.END)
        start_idx = max(0, len(self.recorded_actions) - 50)
        for i, action in enumerate(self.recorded_actions[start_idx:], start=start_idx + 1):
            text = f"{i:3d}. {self._format_action(action)}"
            self.actions_list.insert(tk.END, text)

        self.action_count_label.config(text=f"Actions: {len(self.recorded_actions)}")
        if self.recorded_actions:
            self.actions_list.see(tk.END)

    def _save_macro(self):
        """Save recorded actions as a macro"""
        if not self.recorded_actions:
            messagebox.showwarning("No Actions", "Record some actions first")
            return

        # Dialog for macro details
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Macro")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Macro Name:").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=5)

        ttk.Label(dialog, text="Gesture Name (optional):").pack(pady=5)
        gesture_entry = ttk.Entry(dialog, width=40)
        gesture_entry.pack(pady=5)

        ttk.Label(dialog, text="Description (optional):").pack(pady=5)
        desc_text = tk.Text(dialog, height=4, width=40)
        desc_text.pack(pady=5)

        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Invalid", "Enter a name", parent=dialog)
                return

            macro = Macro(
                name=name,
                actions=self.recorded_actions.copy(),
                device_width=self.parser.max_x,
                device_height=self.parser.max_y,
                created_at=datetime.now().isoformat(),
                gesture_name=gesture_entry.get().strip(),
                description=desc_text.get('1.0', tk.END).strip()
            )

            self.db.save_macro(macro)
            self.macros.append(macro)
            self._update_macros_display()
            self._log(f"💾 Saved: {name}")
            dialog.destroy()
            messagebox.showinfo("Saved", f"Macro '{name}' saved with {len(macro.actions)} actions")

        ttk.Button(dialog, text="Save", command=save).pack(pady=10)

    def _load_data(self):
        """Load macros and profiles from database"""
        self.macros = self.db.load_macros()
        self._update_macros_display()

        self.profiles = self.db.load_profiles()
        self._update_profiles_display()

        if self.macros:
            self._log(f"✓ Loaded {len(self.macros)} macros")
        if self.profiles:
            self._log(f"✓ Loaded {len(self.profiles)} profiles")

    def _update_macros_display(self):
        """Update the macros list display"""
        self.macros_list.delete(0, tk.END)
        for macro in self.macros:
            taps = sum(1 for a in macro.actions if a.action_type == 'TAP')
            holds = sum(1 for a in macro.actions if a.action_type == 'HOLD')
            swipes = sum(1 for a in macro.actions if a.action_type == 'SWIPE')
            multi = sum(1 for a in macro.actions if a.action_type == 'MULTI_TAP')

            parts = []
            if taps: parts.append(f"{taps}T")
            if holds: parts.append(f"{holds}H")
            if swipes: parts.append(f"{swipes}S")
            if multi: parts.append(f"{multi}M")

            gesture = f" [{macro.gesture_name}]" if macro.gesture_name else ""
            text = f"{macro.name:20s}{gesture} [{'/'.join(parts)}]"
            self.macros_list.insert(tk.END, text)

    def _on_macro_select(self, event):
        """Handle macro selection"""
        selection = self.macros_list.curselection()
        if not selection:
            return

        macro = self.macros[selection[0]]

        type_counts = {}
        for a in macro.actions:
            type_counts[a.action_type] = type_counts.get(a.action_type, 0) + 1

        total_duration = sum(a.duration for a in macro.actions)
        total_delays = sum(a.delay_before for a in macro.actions)

        details = f"Name: {macro.name}\n"
        if macro.gesture_name:
            details += f"Gesture: {macro.gesture_name}\n"
        details += f"Device: {macro.device_width}x{macro.device_height}\n"
        details += f"Created: {macro.created_at}\n"
        details += f"Actions: {len(macro.actions)} | " + " | ".join(f"{k}:{v}" for k,v in type_counts.items()) + "\n"
        details += f"Duration: {total_duration:.2f}s | Total: {total_duration + total_delays:.2f}s\n"
        if macro.description:
            details += f"\n{macro.description}\n"

        self.macro_detail.delete('1.0', tk.END)
        self.macro_detail.insert('1.0', details)

    def _toggle_playback(self):
        """Toggle playback state"""
        if self.is_playing:
            self.is_playing = False
            self.play_btn.config(text="▶️ Play (F11)")
            self.playback_status.config(text="⏹️ Stopped")
            self._log("⏹️ Playback stopped by user")
        else:
            self._play_macro()

    def _play_macro(self):
        """Play the selected macro"""
        if self.is_playing:
            return

        selection = self.macros_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a macro first")
            return

        if not self.adb.device_id:
            messagebox.showwarning("No Device", "Connect to a device first")
            return

        macro = self.macros[selection[0]]
        speed = self.speed_var.get()
        scale = self.scale_var.get()
        loops = self.loop_var.get()

        self.is_playing = True
        self.play_btn.config(text="⏹️ Stop")

        def player():
            start_time = time.time()
            try:
                scale_x = self.adb.screen_width / macro.device_width if scale else 1.0
                scale_y = self.adb.screen_height / macro.device_height if scale else 1.0

                self._log(f"▶️ Playing '{macro.name}' {loops}x @ {speed}x speed")

                for loop in range(loops):
                    if not self.is_playing:
                        break

                    if loops > 1:
                        self.playback_status.config(text=f"▶️ Loop {loop+1}/{loops}")
                        self._log(f"Loop {loop+1}/{loops}")

                    for i, action in enumerate(macro.actions):
                        if not self.is_playing:
                            break

                        # Wait for delay
                        if action.delay_before > 0:
                            delay = action.delay_before / speed
                            remaining = delay
                            while remaining > 0 and self.is_playing:
                                time.sleep(min(0.1, remaining))
                                remaining -= 0.1
                            if not self.is_playing:
                                break

                        # Execute action
                        x1 = int(action.start_x * scale_x)
                        y1 = int(action.start_y * scale_y)

                        if action.action_type == 'TAP':
                            self.adb.execute_tap(x1, y1, action.humanize)
                        elif action.action_type == 'HOLD':
                            self.adb.execute_hold(x1, y1, action.duration, action.humanize)
                        elif action.action_type == 'SWIPE':
                            x2 = int(action.end_x * scale_x)
                            y2 = int(action.end_y * scale_y)
                            duration_ms = int(action.duration * 1000)
                            self.adb.execute_swipe(x1, y1, x2, y2, duration_ms, action.humanize)
                        elif action.action_type == 'MULTI_TAP':
                            positions = [(x1, y1)]
                            for sx, sy in action.secondary_fingers:
                                positions.append((int(sx * scale_x), int(sy * scale_y)))
                            self.adb.execute_multi_tap(positions, action.humanize)

                        progress = f"{i+1}/{len(macro.actions)}"
                        self.playback_status.config(text=f"▶️ {progress}")

                        time.sleep(0.02 / speed)

                if self.is_playing:
                    duration = time.time() - start_time
                    self.db.update_analytics(macro.name, duration)
                    self._log("✓ Playback complete!")
                    self.playback_status.config(text="✓ Done")

            except Exception as e:
                self._log(f"❌ Playback error: {e}")
                self.playback_status.config(text="❌ Error")
            finally:
                self.is_playing = False
                self.play_btn.config(text="▶️ Play (F11)")

        threading.Thread(target=player, daemon=True).start()

    def _edit_macro(self):
        """Edit the selected macro"""
        selection = self.macros_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a macro first")
            return

        macro = self.macros[selection[0]]

        def save_edited(edited_macro):
            self.macros[selection[0]] = edited_macro
            self.db.save_macro(edited_macro)
            self._update_macros_display()
            self._log(f"✏️ Edited: {edited_macro.name}")

        MacroTimelineEditor(self.root, macro, save_edited)

    def _export_macro(self):
        """Export the selected macro to a file"""
        selection = self.macros_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a macro first")
            return

        macro = self.macros[selection[0]]

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{macro.name}.json"
        )

        if filepath:
            with open(filepath, 'w') as f:
                json.dump({
                    'name': macro.name,
                    'device_width': macro.device_width,
                    'device_height': macro.device_height,
                    'created_at': macro.created_at,
                    'gesture_name': macro.gesture_name,
                    'description': macro.description,
                    'actions': [asdict(a) for a in macro.actions]
                }, f, indent=2)
            self._log(f"📤 Exported: {macro.name} → {filepath}")
            messagebox.showinfo("Exported", f"Exported to:\n{filepath}")

    def _import_macro(self):
        """Import a macro from a file"""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath) as f:
                    data = json.load(f)

                actions = []
                for a_data in data['actions']:
                    # Ensure backward compatibility
                    if 'delay_before' not in a_data:
                        a_data['delay_before'] = 0.0
                    if 'slot' not in a_data:
                        a_data['slot'] = 0
                    if 'secondary_fingers' not in a_data:
                        a_data['secondary_fingers'] = []
                    if 'humanize' not in a_data:
                        a_data['humanize'] = False
                    actions.append(TouchAction(**a_data))

                macro = Macro(
                    name=data['name'],
                    actions=actions,
                    device_width=data['device_width'],
                    device_height=data['device_height'],
                    created_at=data['created_at'],
                    gesture_name=data.get('gesture_name', ''),
                    description=data.get('description', '')
                )

                self.db.save_macro(macro)
                self.macros.append(macro)
                self._update_macros_display()
                self._log(f"📥 Imported: {macro.name}")
                messagebox.showinfo("Imported", f"Imported macro:\n{macro.name}")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import:\n{str(e)}")

    def _delete_macro(self):
        """Delete the selected macro"""
        selection = self.macros_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a macro first")
            return

        macro = self.macros[selection[0]]
        if messagebox.askyesno("Delete", f"Delete macro '{macro.name}'?"):
            self.db.delete_macro(macro.name)
            del self.macros[selection[0]]
            self._update_macros_display()
            self.macro_detail.delete('1.0', tk.END)
            self._log(f"🗑️ Deleted: {macro.name}")

    def _save_profile(self):
        """Save current device configuration as a profile"""
        if not self.adb.device_id:
            messagebox.showwarning("No Device", "Connect to a device first")
            return

        name = simpledialog.askstring("Profile Name", "Enter profile name:", parent=self.root)
        if not name:
            return

        profile = Profile(
            name=name,
            device_id=self.adb.device_id,
            screen_width=self.adb.screen_width,
            screen_height=self.adb.screen_height,
            touch_device=self.adb.touch_device or "",
            macros=[m.name for m in self.macros],
            created_at=datetime.now().isoformat()
        )

        self.db.save_profile(profile)
        self.profiles.append(profile)
        self._update_profiles_display()
        self._log(f"💾 Profile saved: {name}")
        messagebox.showinfo("Saved", f"Profile '{name}' saved")

    def _load_profile(self):
        """Load the selected profile"""
        selection = self.profiles_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a profile first")
            return

        profile = self.profiles[selection[0]]

        self.adb.device_id = profile.device_id
        self.adb.screen_width = profile.screen_width
        self.adb.screen_height = profile.screen_height
        self.adb.touch_device = profile.touch_device

        self.parser.max_x = profile.screen_width
        self.parser.max_y = profile.screen_height
        self.gesture_canvas.set_device_size(profile.screen_width, profile.screen_height)

        self.current_profile = profile
        self.profile_label.config(text=f"Profile: {profile.name}")

        self._log(f"👤 Loaded profile: {profile.name}")
        messagebox.showinfo("Loaded", f"Profile '{profile.name}' loaded")

    def _delete_profile(self):
        """Delete the selected profile"""
        selection = self.profiles_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a profile first")
            return

        profile = self.profiles[selection[0]]
        if messagebox.askyesno("Delete", f"Delete profile '{profile.name}'?"):
            self.db.delete_profile(profile.name)
            del self.profiles[selection[0]]
            self._update_profiles_display()
            self._log(f"🗑️ Deleted profile: {profile.name}")

    def _update_profiles_display(self):
        """Update the profiles list display"""
        self.profiles_list.delete(0, tk.END)
        for profile in self.profiles:
            text = f"{profile.name:20s} | {profile.device_id:15s} | {profile.screen_width}x{profile.screen_height}"
            self.profiles_list.insert(tk.END, text)

    def _show_analytics(self):
        """Show the analytics window"""
        AnalyticsWindow(self.root, self.db)

    def _clear_log(self):
        """Clear the log"""
        if messagebox.askyesno("Clear Log", "Clear the log?"):
            self.log_text.delete('1.0', tk.END)
            self._log("Log cleared")

    def _cleanup(self):
        """Clean up resources before closing"""
        print("Starting cleanup...")

        # Stop recording and playback
        self.is_recording = False
        self.is_playing = False

        # Delete all tkinter Variables before closing
        try:
            if hasattr(self, 'device_var'):
                del self.device_var
            if hasattr(self, 'humanize_var'):
                del self.humanize_var
            if hasattr(self, 'speed_var'):
                del self.speed_var
            if hasattr(self, 'loop_var'):
                del self.loop_var
            if hasattr(self, 'scale_var'):
                del self.scale_var
            if hasattr(self, 'auto_scroll_var'):
                del self.auto_scroll_var
            print("✓ Variables deleted")
        except Exception as e:
            print(f"Warning during variable cleanup: {e}")

        # Shutdown executor
        try:
            if hasattr(self, 'adb') and hasattr(self.adb, 'executor'):
                self.adb.executor.shutdown(wait=False)
                print("✓ Executor shutdown")
        except Exception as e:
            print(f"Warning during executor shutdown: {e}")

        # Close database
        try:
            if hasattr(self, 'db'):
                self.db.close()
                print("✓ Database closed")
        except Exception as e:
            print(f"Warning during database closure: {e}")

        # Destroy window
        try:
            self.root.destroy()
            print("✓ Window destroyed")
        except Exception as e:
            print(f"Warning during window destruction: {e}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    app = TouchLoggerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
