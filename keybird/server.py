#!/usr/bin/env python3
# Pi Keyboard Bridge - Text to HID + Pass-through + Learning Mode

import time
import os
import threading
import select
import json
from collections import deque
from flask import Flask, request, render_template, jsonify

import glob

# Try to import evdev for pass-through (optional)
try:
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    print("⚠️  evdev not available - pass-through mode disabled")

HID_PATH = "/dev/hidg0"
HID_MEDIA_PATH = "/dev/hidg1"
HID_MOUSE_PATH = "/dev/hidg2"
PROFILES_FILE = "/home/pi/keyboard_profiles.json"
MAPPINGS_FILE = "/home/pi/keyboard_mappings.json"
CALIBRATIONS_FILE = "/home/pi/trackpad_calibrations.json"

# Learning mode - stores recent unmapped keys for UI display
unmapped_keys_buffer = deque(maxlen=50)  # Last 50 unmapped keys

# ===== EMULATION PROFILES (VID/PID only) =====
def load_emulation_profiles():
    """Load saved emulation profiles (keyboards we can pretend to be)"""
    if not os.path.exists(PROFILES_FILE):
        # Create default profiles
        defaults = {
            "profiles": [
                {
                    "id": "logitech_4049",
                    "name": "Logitech Unifying Receiver (Generic)",
                    "vid": "046d",
                    "pid": "4049",
                    "manufacturer": "Logitech",
                    "product": "Logitech Unifying Receiver"
                }
            ],
            "active_profile_id": "logitech_4049"
        }
        save_emulation_profiles(defaults)
        return defaults
    try:
        with open(PROFILES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"profiles": [], "active_profile_id": None}

def save_emulation_profiles(data):
    """Save emulation profiles to file"""
    with open(PROFILES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

emulation_profiles = load_emulation_profiles()

# ===== PHYSICAL KEYBOARD MAPPINGS (Per keyboard) =====
def load_keyboard_mappings():
    """Load per-keyboard custom mappings"""
    if not os.path.exists(MAPPINGS_FILE):
        return {}
    try:
        with open(MAPPINGS_FILE, 'r') as f:
            data = json.load(f)
            # Convert string codes back to ints for each keyboard
            result = {}
            for kbd_id, kbd_data in data.items():
                result[kbd_id] = {
                    'keyboard_name': kbd_data.get('keyboard_name', 'Unknown'),
                    'custom_mappings': {int(k): v for k, v in kbd_data.get('custom_mappings', {}).items()}
                }
            return result
    except:
        return {}

def save_keyboard_mappings(data):
    """Save per-keyboard mappings to file"""
    # Convert int codes to strings for JSON
    export_data = {}
    for kbd_id, kbd_data in data.items():
        export_data[kbd_id] = {
            'keyboard_name': kbd_data.get('keyboard_name', 'Unknown'),
            'custom_mappings': {str(k): v for k, v in kbd_data.get('custom_mappings', {}).items()}
        }
    with open(MAPPINGS_FILE, 'w') as f:
        json.dump(export_data, f, indent=2)

keyboard_mappings = load_keyboard_mappings()
active_physical_keyboard_id = None  # Will be set when pass-through starts

# ===== KEY LISTENING MODE (for mapping) =====
listening_keyboard_id = None  # Which keyboard we're listening to for mapping
listening_lock = threading.Lock()  # Lock for listening state
captured_key_buffer = deque(maxlen=10)  # Store captured keys for mapping

# ===== TRACKPAD CALIBRATIONS =====
def load_calibrations():
    """Load saved trackpad calibrations"""
    if not os.path.exists(CALIBRATIONS_FILE):
        return {
            "calibrations": [],
            "active_calibration_id": None
        }
    try:
        with open(CALIBRATIONS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"calibrations": [], "active_calibration_id": None}

def save_calibrations(data):
    """Save trackpad calibrations to file"""
    with open(CALIBRATIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

calibrations_data = load_calibrations()

# Auto-detect UDC path (works on Pi 4, Pi 5, Pi Zero, etc.)
def find_udc_state_path():
    udc_paths = glob.glob("/sys/class/udc/*/state")
    if udc_paths:
        return udc_paths[0]
    return None

UDC_STATE_PATH = find_udc_state_path()

# Initialize Flask with template and static folders in package directory
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# ---------------- Keyboard mapping basics ----------------
SHIFT = 0x02
KEYMAP = {
    **{c: (0x00, 0x04+i) for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")},
    '1': (0x00, 0x1E),'2': (0x00, 0x1F),'3': (0x00, 0x20),'4': (0x00, 0x21),'5': (0x00, 0x22),
    '6': (0x00, 0x23),'7': (0x00, 0x24),'8': (0x00, 0x25),'9': (0x00, 0x26),'0': (0x00, 0x27),
    ' ': (0x00, 0x2C), '\n': (0x00, 0x28), '\r': (0x00, 0x28), '\t': (0x00, 0x2B), '\b': (0x00, 0x2A),
    '-': (0x00, 0x2D), '=': (0x00, 0x2E), '[': (0x00, 0x2F), ']': (0x00, 0x30),
    '\\': (0x00, 0x31), ';': (0x00, 0x33), "'": (0x00, 0x34), '`': (0x00, 0x35),
    ',': (0x00, 0x36), '.': (0x00, 0x37), '/': (0x00, 0x38),
}
SHIFT_MAP = {
    '!':'1','@':'2','#':'3','$':'4','%':'5','^':'6','&':'7','*':'8','(':'9',')':'0',
    '_':'-','+':'=','{':'[','}':']','|':'\\',':':';','"':"'",'~':'`','<':',','>':'.','?':'/'
}

def char_to_key(ch):
    if ch in KEYMAP: return KEYMAP[ch]
    if 'A' <= ch <= 'Z':
        _, base = KEYMAP[ch.lower()]
        return (SHIFT, base)
    if ch in SHIFT_MAP:
        _, base = KEYMAP[SHIFT_MAP[ch]]
        return (SHIFT, base)
    return None

def emit_report(hid, modifiers, keycode):
    hid.write(bytes([modifiers, 0x00, keycode, 0, 0, 0, 0, 0]))
    hid.flush()

def tap_key(hid, modifiers, keycode, delay=0.004):
    emit_report(hid, modifiers, keycode); time.sleep(delay)
    emit_report(hid, 0x00, 0x00);        time.sleep(delay)

def get_usb_state():
    """Check if a USB host is connected"""
    try:
        if UDC_STATE_PATH is None:
            return "no_udc"
        with open(UDC_STATE_PATH, 'r') as f:
            state = f.read().strip()
            return state
    except:
        return "unknown"

def send_text_as_keys(text):
    with open(HID_PATH, "wb", buffering=0) as hid:
        for ch in text:
            if ch == '\r': ch = '\n'
            pair = char_to_key(ch)
            if pair:
                mods, kc = pair
                tap_key(hid, mods, kc)

# --------------- Pass-through Mode --------------------
PASSTHROUGH_ENABLED = False
passthrough_thread = None

MOUSE_PASSTHROUGH_ENABLED = False
mouse_passthrough_thread = None

def detect_mice():
    """Detect all physical mice plugged into the Pi"""
    if not EVDEV_AVAILABLE:
        return []
    
    mice = []
    for path in glob.glob("/dev/input/event*"):
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            
            # Check if it's a mouse (has relative X/Y movement)
            rel_caps = caps.get(ecodes.EV_REL, [])
            if ecodes.REL_X in rel_caps and ecodes.REL_Y in rel_caps:
                # Filter out HDMI and other non-mouse devices
                if 'hdmi' in dev.name.lower() or 'vc4' in dev.name.lower():
                    continue
                # Get USB device info if available
                vid = None
                pid = None
                
                # Try to extract VID/PID from sysfs (same method as keyboard)
                try:
                    sysfs_path = dev.path.replace('/dev/input/', '/sys/class/input/')
                    device_path = os.path.realpath(f"{sysfs_path}/device")
                    
                    current = device_path
                    for _ in range(10):
                        vid_path = os.path.join(current, "idVendor")
                        pid_path = os.path.join(current, "idProduct")
                        
                        if os.path.exists(vid_path) and os.path.exists(pid_path):
                            with open(vid_path, 'r') as f:
                                vid = f.read().strip()
                            with open(pid_path, 'r') as f:
                                pid = f.read().strip()
                            break
                        
                        parent = os.path.dirname(current)
                        if parent == current:
                            break
                        current = parent
                except:
                    pass
                
                mice.append({
                    'name': dev.name,
                    'path': dev.path,
                    'vid': vid,
                    'pid': pid,
                    'phys': dev.phys,
                    'uniq': dev.uniq,
                })
        except Exception:
            continue
    
    return mice


def detect_keyboards():
    """Detect all physical keyboards plugged into the Pi"""
    if not EVDEV_AVAILABLE:
        return []
    
    keyboards = []
    for path in glob.glob("/dev/input/event*"):
        try:
            dev = InputDevice(path)
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            
            # Check if it's a keyboard (has letters and Enter)
            if ecodes.KEY_A in caps and ecodes.KEY_ENTER in caps:
                # Get USB device info if available
                vid = None
                pid = None
                
                # Try to extract VID/PID from sysfs
                try:
                    # Method 1: Walk up from /sys/class/input/eventX
                    sysfs_path = dev.path.replace('/dev/input/', '/sys/class/input/')
                    device_path = os.path.realpath(f"{sysfs_path}/device")
                    
                    # Look for idVendor/idProduct in parent directories
                    current = device_path
                    for _ in range(10):  # Search up to 10 levels
                        vid_path = os.path.join(current, "idVendor")
                        pid_path = os.path.join(current, "idProduct")
                        
                        if os.path.exists(vid_path) and os.path.exists(pid_path):
                            with open(vid_path, 'r') as f:
                                vid = f.read().strip()
                            with open(pid_path, 'r') as f:
                                pid = f.read().strip()
                            break
                        
                        # Stop at root
                        parent = os.path.dirname(current)
                        if parent == current:
                            break
                        current = parent
                    
                    # Method 2: Try using device info from evdev
                    if not vid or not pid:
                        # Parse from device physical address (e.g., "usb-0000:01:00.0-1.3/input0")
                        if dev.phys and 'usb' in dev.phys.lower():
                            # Try to find in /sys/bus/usb/devices
                            for usb_dev in glob.glob("/sys/bus/usb/devices/*"):
                                try:
                                    with open(f"{usb_dev}/idVendor", 'r') as f:
                                        test_vid = f.read().strip()
                                    with open(f"{usb_dev}/idProduct", 'r') as f:
                                        test_pid = f.read().strip()
                                    with open(f"{usb_dev}/product", 'r') as f:
                                        product_name = f.read().strip()
                                    
                                    # Check if this matches our device name
                                    if dev.name in product_name or product_name in dev.name:
                                        vid = test_vid
                                        pid = test_pid
                                        break
                                except:
                                    continue
                except:
                    pass
                
                keyboards.append({
                    'name': dev.name,
                    'path': dev.path,
                    'vid': vid,
                    'pid': pid,
                    'phys': dev.phys,
                    'uniq': dev.uniq,
                })
        except Exception as e:
            continue
    
    return keyboards

if EVDEV_AVAILABLE:
    # Complete keyboard mapping (Linux evdev → USB HID Usage codes)
    LINUX_TO_HID = {
        # Letters (a-z)
        ecodes.KEY_A: 0x04, ecodes.KEY_B: 0x05, ecodes.KEY_C: 0x06, ecodes.KEY_D: 0x07,
        ecodes.KEY_E: 0x08, ecodes.KEY_F: 0x09, ecodes.KEY_G: 0x0A, ecodes.KEY_H: 0x0B,
        ecodes.KEY_I: 0x0C, ecodes.KEY_J: 0x0D, ecodes.KEY_K: 0x0E, ecodes.KEY_L: 0x0F,
        ecodes.KEY_M: 0x10, ecodes.KEY_N: 0x11, ecodes.KEY_O: 0x12, ecodes.KEY_P: 0x13,
        ecodes.KEY_Q: 0x14, ecodes.KEY_R: 0x15, ecodes.KEY_S: 0x16, ecodes.KEY_T: 0x17,
        ecodes.KEY_U: 0x18, ecodes.KEY_V: 0x19, ecodes.KEY_W: 0x1A, ecodes.KEY_X: 0x1B,
        ecodes.KEY_Y: 0x1C, ecodes.KEY_Z: 0x1D,
        
        # Numbers
        ecodes.KEY_1: 0x1E, ecodes.KEY_2: 0x1F, ecodes.KEY_3: 0x20, ecodes.KEY_4: 0x21,
        ecodes.KEY_5: 0x22, ecodes.KEY_6: 0x23, ecodes.KEY_7: 0x24, ecodes.KEY_8: 0x25,
        ecodes.KEY_9: 0x26, ecodes.KEY_0: 0x27,
        
        # Special keys
        ecodes.KEY_ENTER: 0x28, ecodes.KEY_ESC: 0x29, ecodes.KEY_BACKSPACE: 0x2A,
        ecodes.KEY_TAB: 0x2B, ecodes.KEY_SPACE: 0x2C,
        
        # Punctuation
        ecodes.KEY_MINUS: 0x2D, ecodes.KEY_EQUAL: 0x2E, ecodes.KEY_LEFTBRACE: 0x2F, 
        ecodes.KEY_RIGHTBRACE: 0x30, ecodes.KEY_BACKSLASH: 0x31, ecodes.KEY_SEMICOLON: 0x33, 
        ecodes.KEY_APOSTROPHE: 0x34, ecodes.KEY_GRAVE: 0x35, ecodes.KEY_COMMA: 0x36, 
        ecodes.KEY_DOT: 0x37, ecodes.KEY_SLASH: 0x38,
        
        # Lock keys
        ecodes.KEY_CAPSLOCK: 0x39, ecodes.KEY_NUMLOCK: 0x53, ecodes.KEY_SCROLLLOCK: 0x47,
        
        # Function keys (F1-F12)
        ecodes.KEY_F1: 0x3A, ecodes.KEY_F2: 0x3B, ecodes.KEY_F3: 0x3C, ecodes.KEY_F4: 0x3D,
        ecodes.KEY_F5: 0x3E, ecodes.KEY_F6: 0x3F, ecodes.KEY_F7: 0x40, ecodes.KEY_F8: 0x41,
        ecodes.KEY_F9: 0x42, ecodes.KEY_F10: 0x43, ecodes.KEY_F11: 0x44, ecodes.KEY_F12: 0x45,
        
        # Navigation cluster
        ecodes.KEY_SYSRQ: 0x46, ecodes.KEY_PAUSE: 0x48,
        ecodes.KEY_INSERT: 0x49, ecodes.KEY_HOME: 0x4A, ecodes.KEY_PAGEUP: 0x4B,
        ecodes.KEY_DELETE: 0x4C, ecodes.KEY_END: 0x4D, ecodes.KEY_PAGEDOWN: 0x4E,
        
        # Arrow keys
        ecodes.KEY_RIGHT: 0x4F, ecodes.KEY_LEFT: 0x50, ecodes.KEY_DOWN: 0x51, ecodes.KEY_UP: 0x52,
        
        # Keypad numbers
        ecodes.KEY_KP0: 0x62, ecodes.KEY_KP1: 0x59, ecodes.KEY_KP2: 0x5A, ecodes.KEY_KP3: 0x5B,
        ecodes.KEY_KP4: 0x5C, ecodes.KEY_KP5: 0x5D, ecodes.KEY_KP6: 0x5E, ecodes.KEY_KP7: 0x5F,
        ecodes.KEY_KP8: 0x60, ecodes.KEY_KP9: 0x61,
        
        # Keypad operators
        ecodes.KEY_KPSLASH: 0x54, ecodes.KEY_KPASTERISK: 0x55, ecodes.KEY_KPMINUS: 0x56,
        ecodes.KEY_KPPLUS: 0x57, ecodes.KEY_KPENTER: 0x58, ecodes.KEY_KPDOT: 0x63,
        ecodes.KEY_KPEQUAL: 0x67,
        
        # Application and Windows keys (handled as modifiers above, but can also be standalone)
        ecodes.KEY_MENU: 0x65,  # Application/context menu key
        
        # Additional function keys
        ecodes.KEY_F13: 0x68, ecodes.KEY_F14: 0x69, ecodes.KEY_F15: 0x6A, ecodes.KEY_F16: 0x6B,
        ecodes.KEY_F17: 0x6C, ecodes.KEY_F18: 0x6D, ecodes.KEY_F19: 0x6E, ecodes.KEY_F20: 0x6F,
        ecodes.KEY_F21: 0x70, ecodes.KEY_F22: 0x71, ecodes.KEY_F23: 0x72, ecodes.KEY_F24: 0x73,
        
        # Some keyboards send media as function keys
        # Try mapping common media key codes to available HID codes
        # Note: These may not work as expected with boot keyboard descriptor
        # but we'll try them anyway
    }
    
    # Media keys - Consumer Control usage IDs
    MEDIA_KEY_TO_USAGE = {
        ecodes.KEY_MUTE: 0xE2,
        ecodes.KEY_VOLUMEUP: 0xE9,
        ecodes.KEY_VOLUMEDOWN: 0xEA,
        ecodes.KEY_PLAYPAUSE: 0xCD,
        ecodes.KEY_STOP: 0xB7,
        ecodes.KEY_PREVIOUSSONG: 0xB6,
        ecodes.KEY_NEXTSONG: 0xB5,
        ecodes.KEY_MAIL: 0x18A,
        ecodes.KEY_CALC: 0x192,
        ecodes.KEY_HOMEPAGE: 0x223,
        ecodes.KEY_BACK: 0x224,
        ecodes.KEY_FORWARD: 0x225,
    }
    
    # Suggested HID codes for common unmapped keys
    # This helps users map keys they encounter
    SUGGESTED_MAPPINGS = {
        'KEY_SLEEP': 0x66,
        'KEY_WAKEUP': 0x66,
        'KEY_POWER': 0x66,
        'KEY_102ND': 0x64,  # Non-US backslash
        'KEY_COMPOSE': 0x65, # Menu/Application key
        'KEY_KPCOMMA': 0x85,
        'KEY_RO': 0x87,  # International keys
        'KEY_KATAKANA': 0x88,
        'KEY_HIRAGANA': 0x89,
        'KEY_YEN': 0x89,
        'KEY_HANGEUL': 0x90,
        'KEY_HANJA': 0x91,
        'KEY_KATAKANA_HIRAGANA': 0x88,
        'KEY_LEFTMETA': 0x08,  # Already in modifiers but useful reference
        'KEY_RIGHTMETA': 0x80,
    }
    
    def send_media_key(usage_id):
        """Send a consumer control (media) key"""
        if not os.path.exists(HID_MEDIA_PATH):
            print(f"⚠️  Media key device {HID_MEDIA_PATH} not available")
            return False
        
        try:
            with open(HID_MEDIA_PATH, "wb", buffering=0) as hid:
                # Consumer control report: Report ID (0x01) + Usage (2 bytes, little-endian)
                report = bytes([0x01, usage_id & 0xFF, (usage_id >> 8) & 0xFF])
                hid.write(report)
                hid.flush()
                time.sleep(0.01)
                # Release (send zeros)
                hid.write(bytes([0x01, 0x00, 0x00]))
                hid.flush()
            return True
        except Exception as e:
            print(f"❌ Media key error: {e}")
            return False
    
    MOD_LCTRL=0x01; MOD_LSHIFT=0x02; MOD_LALT=0x04; MOD_LGUI=0x08
    MOD_RCTRL=0x10; MOD_RSHIFT=0x20; MOD_RALT=0x40; MOD_RGUI=0x80
    MOD_KEYS = {
        ecodes.KEY_LEFTCTRL: MOD_LCTRL, ecodes.KEY_LEFTSHIFT: MOD_LSHIFT,
        ecodes.KEY_LEFTALT: MOD_LALT, ecodes.KEY_LEFTMETA: MOD_LGUI,
        ecodes.KEY_RIGHTCTRL: MOD_RCTRL, ecodes.KEY_RIGHTSHIFT: MOD_RSHIFT,
        ecodes.KEY_RIGHTALT: MOD_RALT, ecodes.KEY_RIGHTMETA: MOD_RGUI,
    }
    
    class KeyState:
        def __init__(self):
            self.mod = 0
            self.keys = []
        def press(self, keycode):
            if keycode not in self.keys and len(self.keys) < 6:
                self.keys.append(keycode)
        def release(self, keycode):
            if keycode in self.keys:
                self.keys.remove(keycode)
        def report(self):
            arr = [self.mod, 0] + self.keys[:6] + [0]*(6-len(self.keys))
            return bytes(arr)
    
    def pass_through_loop():
        global PASSTHROUGH_ENABLED, active_physical_keyboard_id
        # Find ALL keyboard devices
        keyboards = []
        keyboard_map = {}  # Map fd -> (device, kbd_id)
        
        # First pass: collect all keyboard devices and group by uniq ID
        keyboard_devices = {}  # uniq -> list of (device, path, name)
        
        event_paths = sorted(glob.glob("/dev/input/event*"))
        
        for path in event_paths:
            try:
                cand = InputDevice(path)
                caps = cand.capabilities().get(ecodes.EV_KEY, [])
                # Look for keyboard (has A and Enter keys)
                if ecodes.KEY_A in caps and ecodes.KEY_ENTER in caps:
                    uniq_key = cand.uniq if cand.uniq else f"no_uniq_{cand.name}"
                    if uniq_key not in keyboard_devices:
                        keyboard_devices[uniq_key] = []
                    keyboard_devices[uniq_key].append((cand, path, cand.name))
            except Exception as e:
                print(f"⚠️  Skipped {path}: {e}", flush=True)
                continue
        
        # Second pass: for each unique device, pick the best name and create unified kbd_id
        for uniq_key, devices in keyboard_devices.items():
            # Pick the "best" name (prefer shorter, or one without "Keyboard" suffix)
            best_name = None
            best_device = None
            for device, path, name in devices:
                if best_name is None:
                    best_name = name
                    best_device = device
                elif len(name) < len(best_name):
                    # Prefer shorter name
                    best_name = name
                    best_device = device
                elif "Keyboard" not in name and "Keyboard" in best_name:
                    # Prefer name without "Keyboard" suffix
                    best_name = name
                    best_device = device
            
            # Create unified keyboard ID
            if uniq_key.startswith("no_uniq_"):
                kbd_id = best_name
            else:
                kbd_id = f"{best_name}_{uniq_key}"
            
            # Ensure this keyboard has an entry in mappings
            if kbd_id not in keyboard_mappings:
                keyboard_mappings[kbd_id] = {
                    'keyboard_name': best_name,
                    'custom_mappings': {}
                }
                save_keyboard_mappings(keyboard_mappings)
            
            # Add all devices for this keyboard (monitor all interfaces)
            for device, path, name in devices:
                keyboards.append(device)
                keyboard_map[device.fd] = (device, kbd_id)
                if name != best_name:
                    print(f"🎹 Pass-through monitoring: {name} ({path}) → merged with {best_name}", flush=True)
                else:
                    print(f"🎹 Pass-through monitoring: {name} ({path})", flush=True)
            
            print(f"   Mappings: {len(keyboard_mappings[kbd_id]['custom_mappings'])}", flush=True)
        if not keyboards:
            print("⚠️  No keyboards found for pass-through; waiting...")
            time.sleep(3)
            if PASSTHROUGH_ENABLED:
                return pass_through_loop()
            return
        
        ks = KeyState()
        print(f"✅ Pass-through mode ACTIVE - monitoring {len(keyboards)} keyboard(s)", flush=True)
        
        try:
            with open(HID_PATH, "wb", buffering=0) as hid:
                while PASSTHROUGH_ENABLED:
                    # Monitor all keyboard file descriptors
                    fds = [kbd.fd for kbd in keyboards]
                    r, _, _ = select.select(fds, [], [], 0.5)
                    if not r:
                        continue
                    
                    # Process events from whichever keyboard(s) have data
                    for fd in r:
                        dev, kbd_id = keyboard_map[fd]
                        active_physical_keyboard_id = kbd_id  # Update active keyboard
                        
                        for ev in dev.read():
                            if not PASSTHROUGH_ENABLED:
                                break
                            if ev.type != ecodes.EV_KEY:
                                continue
                            
                            kev = categorize(ev)
                            code = kev.scancode
                            val = kev.keystate  # 0=up,1=down,2=hold
                            
                            # Check if we're in listening mode for this keyboard
                            with listening_lock:
                                is_listening = (listening_keyboard_id == kbd_id)
                            
                            # Handle modifier keys
                            if code in MOD_KEYS:
                                bit = MOD_KEYS[code]
                                if val:
                                    ks.mod |= bit
                                else:
                                    ks.mod &= ~bit
                                
                                # If listening, suppress modifier keys but still track state
                                if is_listening:
                                    # Still track modifier state for combinations, but don't send
                                    continue
                                
                                hid.write(ks.report())
                                hid.flush()
                                continue
                            
                            # If listening mode is active for this keyboard, capture the key
                            if is_listening and val == 1:  # Only capture on key down
                                key_name = ecodes.KEY.get(code, f"KEY_{code}")
                                mod_names = []
                                if ks.mod & 1: mod_names.append('Ctrl')
                                if ks.mod & 2: mod_names.append('Shift')
                                if ks.mod & 4: mod_names.append('Alt')
                                if ks.mod & 8: mod_names.append('Meta')
                                mod_string = '+'.join(mod_names) if mod_names else ''
                                full_name = f"{mod_string}+{key_name}" if mod_string else key_name
                                
                                with listening_lock:
                                    captured_key_buffer.append({
                                        'code': code,
                                        'name': full_name,
                                        'key_name': key_name,
                                        'keyboard_id': kbd_id,
                                        'modifiers': ks.mod,
                                        'timestamp': time.time()
                                    })
                                # Don't pass through the key when capturing - suppress it
                                continue
                            
                            # Check if it's a media key
                            if code in MEDIA_KEY_TO_USAGE:
                                if val == 1:  # Only on key down
                                    usage_id = MEDIA_KEY_TO_USAGE[code]
                                    success = send_media_key(usage_id)
                                    key_name = ecodes.KEY.get(code, f"MEDIA_{code}")
                                    if success:
                                        print(f"🎵 Sent media key: {key_name}")
                                    else:
                                        print(f"⚠️  Media key failed (hidg1 not available): {key_name}")
                                continue
                            
                            # Check custom mappings for THIS keyboard
                            current_kbd_mappings = keyboard_mappings.get(active_physical_keyboard_id, {}).get('custom_mappings', {})
                            if code in current_kbd_mappings:
                                mapping = current_kbd_mappings[code]
                                
                                # Handle 'suppress' type - swallow the key (e.g., YubiKey Enter)
                                if mapping.get('type') == 'suppress':
                                    # Silently ignore this key
                                    key_name = ecodes.KEY.get(code, f"KEY_{code}")
                                    if val == 1:
                                        print(f"🚫 Suppressed key: {key_name} from {keyboard_mappings.get(active_physical_keyboard_id, {}).get('keyboard_name', 'Unknown')}")
                                    continue
                                
                                if val == 1:  # Only on key down
                                    if mapping.get('type') == 'hid':
                                        # User mapped to specific HID code
                                        hid_code = mapping.get('hid_code')
                                        if hid_code:
                                            ks.press(hid_code)
                                            hid.write(ks.report())
                                            hid.flush()
                                    elif mapping.get('type') == 'text':
                                        # User mapped to text string - send it as keystrokes
                                        text = mapping.get('text', '')
                                        if text:
                                            try:
                                                send_text_as_keys(text)
                                                key_name = ecodes.KEY.get(code, f"KEY_{code}")
                                                # Don't log text content (may contain passwords)
                                                print(f"📝 Custom text mapping triggered: {key_name}")
                                            except Exception as e:
                                                print(f"⚠️  Error sending text mapping: {e}")
                                elif val == 0:  # Key up
                                    if mapping.get('type') == 'hid':
                                        hid_code = mapping.get('hid_code')
                                        if hid_code:
                                            ks.release(hid_code)
                                            hid.write(ks.report())
                                            hid.flush()
                                continue
                            
                            # Regular keys
                            hid_code = LINUX_TO_HID.get(code)
                            if hid_code is None:
                                # Log unmapped keys to buffer for UI display (with keyboard ID)
                                if val == 1:  # Only on key down
                                    key_name = ecodes.KEY.get(code, f"UNKNOWN_{code}")
                                    unmapped_keys_buffer.append({
                                        'code': code,
                                        'name': key_name,
                                        'timestamp': time.time(),
                                        'keyboard_id': active_physical_keyboard_id,
                                        'keyboard_name': keyboard_mappings.get(active_physical_keyboard_id, {}).get('keyboard_name', 'Unknown')
                                    })
                                    print(f"⚠️  Unmapped key: {key_name} (code={code}) on {keyboard_mappings.get(active_physical_keyboard_id, {}).get('keyboard_name', 'Unknown')}")
                                continue
                            
                            if val:
                                ks.press(hid_code)
                            else:
                                ks.release(hid_code)
                            
                            hid.write(ks.report())
                            hid.flush()
        except Exception as e:
            print(f"❌ Pass-through error: {e}")
        finally:
            print("⏹️  Pass-through mode STOPPED")

    # Mouse pass-through function
    def mouse_pass_through_loop():
        global MOUSE_PASSTHROUGH_ENABLED, calibration_state
        # Find ALL mouse devices
        mice = []
        mouse_map = {}  # Map fd -> device
        
        for path in glob.glob("/dev/input/event*"):
            try:
                cand = InputDevice(path)
                caps = cand.capabilities()
                rel_caps = caps.get(ecodes.EV_REL, [])
                
                # Check if it's a mouse (has REL_X and REL_Y)
                if ecodes.REL_X in rel_caps and ecodes.REL_Y in rel_caps:
                    # Filter out HDMI and other non-mouse devices
                    if 'hdmi' in cand.name.lower() or 'vc4' in cand.name.lower():
                        continue
                    
                    mice.append(cand)
                    mouse_map[cand.fd] = cand
                    print(f"🖱️  Mouse pass-through monitoring: {cand.name} ({path})", flush=True)
            except Exception:
                continue
        
        if not mice:
            print("⚠️  No mice found for pass-through; waiting...")
            time.sleep(3)
            if MOUSE_PASSTHROUGH_ENABLED:
                return mouse_pass_through_loop()
            return
        
        print(f"✅ Mouse pass-through ACTIVE - monitoring {len(mice)} mouse/mice", flush=True)
        
        # Track button state and position (for calibration)
        buttons_state = 0  # Bit 0=left, 1=right, 2=middle
        
        try:
            with open(HID_MOUSE_PATH, "wb", buffering=0) as hid_mouse:
                while MOUSE_PASSTHROUGH_ENABLED:
                    # Monitor all mouse file descriptors
                    fds = [m.fd for m in mice]
                    r, _, _ = select.select(fds, [], [], 0.5)
                    if not r:
                        continue
                    
                    # Process events from whichever mouse has data
                    for fd in r:
                        dev = mouse_map[fd]
                        
                        for ev in dev.read():
                            if not MOUSE_PASSTHROUGH_ENABLED:
                                break
                            
                            # Handle button events
                            if ev.type == ecodes.EV_KEY:
                                if ev.code == ecodes.BTN_LEFT:
                                    if ev.value == 1:
                                        buttons_state |= 1
                                        # Check if in calibration mode
                                        with calibration_lock:
                                            if calibration_state['active']:
                                                # Record this position
                                                calibration_state['points'].append({
                                                    'x': calibration_state['current_x'],
                                                    'y': calibration_state['current_y']
                                                })
                                                calibration_state['step'] += 1
                                                print(f"🎯 Calibration point {calibration_state['step']}: ({calibration_state['current_x']}, {calibration_state['current_y']})", flush=True)
                                    else:
                                        buttons_state &= ~1
                                elif ev.code == ecodes.BTN_RIGHT:
                                    if ev.value == 1:
                                        buttons_state |= 2
                                    else:
                                        buttons_state &= ~2
                                elif ev.code == ecodes.BTN_MIDDLE:
                                    if ev.value == 1:
                                        buttons_state |= 4
                                    else:
                                        buttons_state &= ~4
                                
                                # Send button state change immediately
                                report = bytes([buttons_state, 0, 0, 0])
                                hid_mouse.write(report)
                                hid_mouse.flush()
                            
                            # Handle movement events
                            elif ev.type == ecodes.EV_REL:
                                dx = 0
                                dy = 0
                                wheel = 0
                                
                                if ev.code == ecodes.REL_X:
                                    dx = max(-127, min(127, ev.value))
                                    # Track position for calibration
                                    with calibration_lock:
                                        calibration_state['current_x'] += ev.value
                                elif ev.code == ecodes.REL_Y:
                                    dy = max(-127, min(127, ev.value))
                                    # Track position for calibration
                                    with calibration_lock:
                                        calibration_state['current_y'] += ev.value
                                elif ev.code == ecodes.REL_WHEEL:
                                    wheel = max(-127, min(127, ev.value))
                                
                                # Convert to unsigned bytes
                                dx_byte = dx if dx >= 0 else (256 + dx)
                                dy_byte = dy if dy >= 0 else (256 + dy)
                                wheel_byte = wheel if wheel >= 0 else (256 + wheel)
                                
                                # Send movement
                                report = bytes([buttons_state, dx_byte, dy_byte, wheel_byte])
                                hid_mouse.write(report)
                                hid_mouse.flush()
        
        except Exception as e:
            print(f"❌ Mouse pass-through error: {e}")
        finally:
            print("⏹️  Mouse pass-through mode STOPPED")

# --------------- Web UI --------------------------

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/usb_status")
def usb_status():
    state = get_usb_state()
    return jsonify(state=state, attached=(state == "configured"))

@app.route("/send_text", methods=["POST"])
def send_text():
    text = request.json.get("text","")
    if not text:
        return jsonify(ok=False, error="No text provided"), 400
    
    # Check USB connection first
    state = get_usb_state()
    if state != "configured":
        return jsonify(ok=False, error=f"USB host not connected (state: {state}). Please plug USB-C cable into a computer."), 400
    
    try:
        send_text_as_keys(text)
        return jsonify(ok=True, sent=len(text))
    except Exception as e:
        error_msg = str(e)
        return jsonify(ok=False, error=error_msg), 500

@app.route("/favicon.ico")
def favicon():
    """Serve favicon from root path (browsers look here automatically)"""
    return app.send_static_file('favicon.ico')

@app.route("/health")
def health():
    state = get_usb_state()
    return jsonify(status="ok", device="hidg0", usb_state=state)

@app.route("/passthrough", methods=["POST", "GET"])
def passthrough_control():
    global PASSTHROUGH_ENABLED, passthrough_thread
    
    if not EVDEV_AVAILABLE:
        return jsonify(ok=False, error="evdev not installed"), 400
    
    if request.method == "GET":
        return jsonify(enabled=PASSTHROUGH_ENABLED, ok=True)
    
    # POST - toggle
    enabled = request.json.get("enabled", False)
    
    if enabled and not PASSTHROUGH_ENABLED:
        # Start pass-through
        PASSTHROUGH_ENABLED = True
        passthrough_thread = threading.Thread(target=pass_through_loop, daemon=True)
        passthrough_thread.start()
        return jsonify(ok=True, enabled=True, message="Pass-through started")
    
    elif not enabled and PASSTHROUGH_ENABLED:
        # Stop pass-through
        PASSTHROUGH_ENABLED = False
        # Thread will exit on its own
        return jsonify(ok=True, enabled=False, message="Pass-through stopped")
    
    return jsonify(ok=True, enabled=PASSTHROUGH_ENABLED)


@app.route("/mouse_passthrough", methods=["POST", "GET"])
def mouse_passthrough_control():
    global MOUSE_PASSTHROUGH_ENABLED, mouse_passthrough_thread
    
    if not EVDEV_AVAILABLE:
        return jsonify(ok=False, error="evdev not installed"), 400
    
    if request.method == "GET":
        return jsonify(enabled=MOUSE_PASSTHROUGH_ENABLED, ok=True)
    
    # POST - toggle
    enabled = request.json.get("enabled", False)
    
    if enabled and not MOUSE_PASSTHROUGH_ENABLED:
        # Start mouse pass-through
        MOUSE_PASSTHROUGH_ENABLED = True
        mouse_passthrough_thread = threading.Thread(target=mouse_pass_through_loop, daemon=True)
        mouse_passthrough_thread.start()
        return jsonify(ok=True, enabled=True, message="Mouse pass-through started")
    
    elif not enabled and MOUSE_PASSTHROUGH_ENABLED:
        # Stop mouse pass-through
        MOUSE_PASSTHROUGH_ENABLED = False
        # Thread will exit on its own
        return jsonify(ok=True, enabled=False, message="Mouse pass-through stopped")
    
    return jsonify(ok=True, enabled=MOUSE_PASSTHROUGH_ENABLED)


@app.route("/detected_mice", methods=["GET"])
def detected_mice_endpoint():
    """Get list of physical mice plugged into the Pi"""
    mice = detect_mice()
    return jsonify(mice=mice, count=len(mice))


# ---- Trackpad Calibration ----
calibration_state = {
    'active': False,
    'step': 0,
    'points': [],  # [(x, y), (x, y), ...]
    'trackpad_width': 500,
    'trackpad_height': 350,
    'current_x': 0,
    'current_y': 0
}
calibration_lock = threading.Lock()

@app.route("/calibration/status", methods=["GET"])
def calibration_status():
    """Get current calibration state"""
    with calibration_lock:
        return jsonify(
            active=calibration_state['active'],
            step=calibration_state['step'],
            points=calibration_state['points']
        )

@app.route("/calibration/start", methods=["POST"])
def start_calibration():
    """Start trackpad calibration process"""
    global calibration_state
    
    data = request.json
    trackpad_width = data.get('trackpad_width', 500)
    trackpad_height = data.get('trackpad_height', 350)
    
    with calibration_lock:
        calibration_state = {
            'active': True,
            'step': 0,
            'points': [],
            'trackpad_width': trackpad_width,
            'trackpad_height': trackpad_height,
            'current_x': 0,
            'current_y': 0
        }
    
    return jsonify(ok=True, message="Calibration started", step=0)

@app.route("/calibration/point", methods=["POST"])
def calibration_point():
    """Record a calibration point"""
    global calibration_state
    
    if not calibration_state['active']:
        return jsonify(ok=False, error="Calibration not active"), 400
    
    data = request.json
    x = data.get('x')
    y = data.get('y')
    
    if x is None or y is None:
        return jsonify(ok=False, error="x and y required"), 400
    
    calibration_state['points'].append({'x': x, 'y': y})
    calibration_state['step'] += 1
    
    # Check if calibration is complete (4 points)
    if calibration_state['step'] >= 4:
        # Calculate sensitivity
        points = calibration_state['points']
        
        # Calculate actual screen dimensions from mouse movements
        # Point 0 (top-left) to Point 1 (top-right) = screen width
        # Point 0 (top-left) to Point 2 (bottom-left) = screen height
        width_traveled = abs(points[1]['x'] - points[0]['x'])
        height_traveled = abs(points[2]['y'] - points[0]['y'])
        
        # Sensitivity = screen size / trackpad size (we need to amplify small trackpad movements!)
        sensitivity_x = width_traveled / calibration_state['trackpad_width'] if width_traveled > 0 else 1.0
        sensitivity_y = height_traveled / calibration_state['trackpad_height'] if height_traveled > 0 else 1.0
        
        # Use average sensitivity
        avg_sensitivity = (sensitivity_x + sensitivity_y) / 2
        
        return jsonify(
            ok=True, 
            complete=True,
            sensitivity=round(avg_sensitivity, 2),
            points=points,
            message=f"Calibration complete! Suggested sensitivity: {avg_sensitivity:.2f}x"
        )
    
    return jsonify(ok=True, step=calibration_state['step'], complete=False)

@app.route("/calibration/cancel", methods=["POST"])
def cancel_calibration():
    """Cancel ongoing calibration"""
    global calibration_state
    calibration_state['active'] = False
    return jsonify(ok=True)

@app.route("/calibration/save", methods=["POST"])
def save_calibration_profile():
    """Save a calibration profile"""
    global calibrations_data
    
    data = request.json
    name = data.get('name', '').strip()
    sensitivity = data.get('sensitivity')
    points = data.get('points', [])
    
    if not name:
        return jsonify(ok=False, error="name required"), 400
    
    # Create unique ID
    cal_id = name.lower().replace(' ', '_')
    
    # Check if exists
    existing = next((c for c in calibrations_data['calibrations'] if c['id'] == cal_id), None)
    if existing:
        # Update existing
        existing['sensitivity'] = sensitivity
        existing['points'] = points
        existing['name'] = name
    else:
        # Create new
        calibrations_data['calibrations'].append({
            'id': cal_id,
            'name': name,
            'sensitivity': sensitivity,
            'points': points,
            'created': time.time()
        })
    
    # Set as active
    calibrations_data['active_calibration_id'] = cal_id
    save_calibrations(calibrations_data)
    
    return jsonify(ok=True, message=f"Calibration '{name}' saved!", calibration_id=cal_id)

@app.route("/calibrations", methods=["GET"])
def get_calibrations():
    """Get all saved calibrations"""
    return jsonify(calibrations_data)

@app.route("/calibrations/<cal_id>/activate", methods=["POST"])
def activate_calibration(cal_id):
    """Set a calibration as active"""
    global calibrations_data
    
    cal = next((c for c in calibrations_data['calibrations'] if c['id'] == cal_id), None)
    if not cal:
        return jsonify(ok=False, error="Calibration not found"), 404
    
    calibrations_data['active_calibration_id'] = cal_id
    save_calibrations(calibrations_data)
    
    return jsonify(ok=True, message=f"Activated '{cal['name']}'", calibration=cal)


# ---- Learning Mode API ----
@app.route("/unmapped_keys", methods=["GET"])
def get_unmapped_keys():
    """Get list of recently detected unmapped keys"""
    keys = list(unmapped_keys_buffer)
    return jsonify(keys=keys, count=len(keys))

@app.route("/unmapped_keys/clear", methods=["POST"])
def clear_unmapped_keys():
    """Clear the unmapped keys buffer"""
    unmapped_keys_buffer.clear()
    return jsonify(ok=True)

@app.route("/map_key", methods=["POST"])
def map_key():
    """Save a custom key mapping for the active physical keyboard"""
    global keyboard_mappings
    
    data = request.json
    code = data.get('code')
    hid_code_str = data.get('hid_code', '').strip()
    kbd_id = data.get('keyboard_id')  # Which keyboard this mapping is for
    
    if code is None:
        return jsonify(ok=False, error="code required"), 400
    
    # Use active keyboard if not specified
    if not kbd_id:
        kbd_id = active_physical_keyboard_id
    
    if not kbd_id:
        return jsonify(ok=False, error="No active keyboard"), 400
    
    # Ensure keyboard exists in mappings
    if kbd_id not in keyboard_mappings:
        keyboard_mappings[kbd_id] = {
            'keyboard_name': 'Unknown',
            'custom_mappings': {}
        }
    
    # Parse HID code (hex string like "0x3A" or "3A")
    try:
        if hid_code_str.startswith('0x') or hid_code_str.startswith('0X'):
            hid_code = int(hid_code_str, 16)
        else:
            hid_code = int(hid_code_str, 16) if hid_code_str else None
    except ValueError:
        return jsonify(ok=False, error="Invalid HID code format"), 400
    
    if hid_code is not None:
        keyboard_mappings[kbd_id]['custom_mappings'][code] = {'type': 'hid', 'hid_code': hid_code}
        save_keyboard_mappings(keyboard_mappings)
        kbd_name = keyboard_mappings[kbd_id]['keyboard_name']
        return jsonify(ok=True, message=f"Mapped code {code} to HID 0x{hid_code:02X} for {kbd_name}")
    
    return jsonify(ok=False, error="No mapping provided"), 400

@app.route("/custom_mappings", methods=["GET"])
def get_custom_mappings():
    """Get all custom mappings for active keyboard"""
    if not active_physical_keyboard_id:
        return jsonify(mappings={}, count=0, keyboard="None")
    
    kbd_data = keyboard_mappings.get(active_physical_keyboard_id, {})
    return jsonify(
        mappings=kbd_data.get('custom_mappings', {}),
        count=len(kbd_data.get('custom_mappings', {})),
        keyboard=kbd_data.get('keyboard_name', 'Unknown'),
        keyboard_id=active_physical_keyboard_id
    )

@app.route("/suggest_mapping", methods=["GET"])
def suggest_mapping():
    """Suggest HID code for a given key name"""
    if not EVDEV_AVAILABLE:
        return jsonify(suggested=None)
    
    key_name = request.args.get('key_name', '')
    
    # Check if we have a suggestion
    suggested_code = SUGGESTED_MAPPINGS.get(key_name)
    
    if suggested_code:
        return jsonify(
            suggested=f"0x{suggested_code:02X}",
            description=f"Common mapping for {key_name}",
            key_name=key_name
        )
    
    # No suggestion - provide reference links
    return jsonify(
        suggested=None,
        reference="https://usb.org/sites/default/files/hut1_4.pdf",
        help_text="Check USB HID Usage Tables (page 83+) for keyboard codes",
        key_name=key_name
    )

@app.route("/detected_keyboards", methods=["GET"])
def detected_keyboards():
    """Get list of physical keyboards plugged into the Pi"""
    keyboards = detect_keyboards()
    
    # Check which keyboards are already in profiles
    for kbd in keyboards:
        if kbd['vid'] and kbd['pid']:
            # Check if this VID:PID combo is already saved
            kbd['in_profiles'] = any(
                p['vid'] == kbd['vid'] and p['pid'] == kbd['pid']
                for p in emulation_profiles['profiles']
            )
        else:
            kbd['in_profiles'] = False
    
    # Try to read current emulation from gadget config
    current_vid = None
    current_pid = None
    current_name = "Unknown"
    current_manufacturer = "Unknown"
    
    try:
        with open('/sys/kernel/config/usb_gadget/g1/idVendor', 'r') as f:
            current_vid = f.read().strip().replace('0x', '')
        with open('/sys/kernel/config/usb_gadget/g1/idProduct', 'r') as f:
            current_pid = f.read().strip().replace('0x', '')
        with open('/sys/kernel/config/usb_gadget/g1/strings/0x409/product', 'r') as f:
            current_name = f.read().strip()
        with open('/sys/kernel/config/usb_gadget/g1/strings/0x409/manufacturer', 'r') as f:
            current_manufacturer = f.read().strip()
    except:
        current_vid = '046d'
        current_pid = '4049'
        current_name = 'Dell WK636 Keyboard'
        current_manufacturer = 'Logitech'
    
    current_emulation = {
        'vid': current_vid,
        'pid': current_pid,
        'name': current_name,
        'manufacturer': current_manufacturer
    }
    
    return jsonify(
        keyboards=keyboards,
        count=len(keyboards),
        currently_emulating=current_emulation
    )

@app.route("/reboot", methods=["POST"])
def reboot_pi():
    """Reboot the Pi - useful after cloning keyboard"""
    try:
        import subprocess
        # Schedule reboot in background so we can return response
        subprocess.Popen(['sudo', 'reboot'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        return jsonify(ok=True, message="Rebooting in 1 second...")
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


# ---- Mouse Emulation ----
@app.route("/mouse_move", methods=["POST"])
def mouse_move():
    """Send mouse movement and/or click"""
    data = request.json
    dx = data.get('dx', 0)  # X movement (-127 to +127)
    dy = data.get('dy', 0)  # Y movement (-127 to +127)
    buttons = data.get('buttons', 0)  # Bit 0=left, 1=right, 2=middle
    wheel = data.get('wheel', 0)  # Scroll wheel
    
    try:
        # Clamp values to signed 8-bit range
        dx = max(-127, min(127, int(dx)))
        dy = max(-127, min(127, int(dy)))
        wheel = max(-127, min(127, int(wheel)))
        
        # Convert to unsigned bytes for struct
        dx_byte = dx if dx >= 0 else (256 + dx)
        dy_byte = dy if dy >= 0 else (256 + dy)
        wheel_byte = wheel if wheel >= 0 else (256 + wheel)
        
        # Mouse HID report: [buttons, X, Y, wheel]
        report = bytes([buttons & 0x07, dx_byte, dy_byte, wheel_byte])
        
        if os.path.exists(HID_MOUSE_PATH):
            with open(HID_MOUSE_PATH, "wb", buffering=0) as mouse:
                mouse.write(report)
            return jsonify(ok=True)
        else:
            return jsonify(ok=False, error="Mouse device not available (hidg2)"), 503
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@app.route("/mouse_click", methods=["POST"])
def mouse_click():
    """Send mouse click (down then up)"""
    data = request.json
    button = data.get('button', 'left')  # 'left', 'right', or 'middle'
    
    button_map = {'left': 1, 'right': 2, 'middle': 4}
    button_bit = button_map.get(button, 1)
    
    try:
        if not os.path.exists(HID_MOUSE_PATH):
            return jsonify(ok=False, error="Mouse device not available"), 503
        
        with open(HID_MOUSE_PATH, "wb", buffering=0) as mouse:
            # Click down
            mouse.write(bytes([button_bit, 0, 0, 0]))
            time.sleep(0.01)  # 10ms click
            # Click up
            mouse.write(bytes([0, 0, 0, 0]))
        
        return jsonify(ok=True, message=f"{button} click sent")
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@app.route("/clone_keyboard", methods=["POST"])
def clone_keyboard():
    """Recreate gadget to emulate a detected keyboard - SAVES TO PROFILES"""
    global emulation_profiles
    
    data = request.json
    vid = data.get('vid', '').strip()
    pid = data.get('pid', '').strip()
    name = data.get('name', 'Unknown Keyboard')
    
    if not vid or not pid:
        return jsonify(ok=False, error="VID and PID required"), 400
    
    try:
        # Extract manufacturer from name
        manufacturer = name.split()[0] if name else "Unknown"
        
        # Create profile ID (safe for filesystem)
        profile_id = f"{manufacturer.lower()}_{pid}"
        
        # Add to emulation profiles if not exists
        existing = next((p for p in emulation_profiles['profiles'] if p['id'] == profile_id), None)
        if not existing:
            new_profile = {
                "id": profile_id,
                "name": name,
                "vid": vid,
                "pid": pid,
                "manufacturer": manufacturer,
                "product": name
            }
            emulation_profiles['profiles'].append(new_profile)
            print(f"💾 Saved new profile: {name}")
        
        # Set as active
        emulation_profiles['active_profile_id'] = profile_id
        save_emulation_profiles(emulation_profiles)
        
        # ALSO save to gadget.conf for immediate use
        config_file = '/home/pi/pi-hid-bridge/scripts/gadget.conf'
        config_content = f"""# USB Gadget Configuration
# This file is read by setup_gadget_composite.sh
# Edit to change which keyboard to emulate

VID=0x{vid}
PID=0x{pid}
PI_MANUFACTURER="{manufacturer}"
PI_PRODUCT="{name}"
"""
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print(f"✅ Activated profile: {name} ({vid}:{pid})")
        
        # Run cleanup
        import subprocess
        subprocess.run(['sudo', 'bash', '/home/pi/pi-hid-bridge/scripts/cleanup_gadget.sh'], check=False)
        time.sleep(1)
        
        # Setup with new VID/PID
        result = subprocess.run(
            ['sudo', 'bash', '/home/pi/pi-hid-bridge/scripts/setup_gadget_composite.sh'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify(
                ok=True, 
                message=f"Now emulating {name} (saved to profiles!)",
                vid=vid,
                pid=pid,
                profile_id=profile_id
            )
        else:
            return jsonify(ok=False, error=result.stderr), 500
            
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ---- Emulation Profile Management ----
@app.route("/emulation_profiles", methods=["GET"])
def get_emulation_profiles():
    """Get all saved emulation profiles"""
    return jsonify(emulation_profiles)

@app.route("/emulation_profiles/switch", methods=["POST"])
def switch_emulation_profile():
    """Switch to a different emulation profile"""
    global emulation_profiles
    
    profile_id = request.json.get('profile_id')
    profile = next((p for p in emulation_profiles['profiles'] if p['id'] == profile_id), None)
    
    if not profile:
        return jsonify(ok=False, error="Profile not found"), 404
    
    # Update gadget.conf with this profile
    config_file = '/home/pi/pi-hid-bridge/scripts/gadget.conf'
    config_content = f"""# USB Gadget Configuration
# This file is read by setup_gadget_composite.sh

VID=0x{profile['vid']}
PID=0x{profile['pid']}
PI_MANUFACTURER="{profile['manufacturer']}"
PI_PRODUCT="{profile['product']}"
"""
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    # Update active profile
    emulation_profiles['active_profile_id'] = profile_id
    save_emulation_profiles(emulation_profiles)
    
    return jsonify(ok=True, message=f"Switched to {profile['name']}. Reboot to apply.", profile=profile)

@app.route("/keyboard_mappings/export", methods=["GET"])
def export_keyboard_mappings():
    """Export mappings for a specific keyboard or all"""
    kbd_id = request.args.get('keyboard_id')
    
    if kbd_id and kbd_id in keyboard_mappings:
        # Export single keyboard
        data = {
            'type': 'keyboard_mapping',
            'keyboard_id': kbd_id,
            **keyboard_mappings[kbd_id]
        }
    else:
        # Export all
        data = {
            'type': 'all_keyboard_mappings',
            'keyboards': keyboard_mappings
        }
    
    return jsonify(data)

@app.route("/keyboard_mappings/all", methods=["GET"])
def get_all_keyboard_mappings():
    """Get all keyboards that have mappings or have been detected"""
    # Group all keyboards (from mappings and detected) by uniq ID
    keyboards_by_uniq = {}  # uniq -> {'best_name': str, 'unified_id': str, 'mappings': dict, 'is_connected': bool}
    
    # First, process saved mappings
    for kbd_id, kbd_data in keyboard_mappings.items():
        # Extract uniq from kbd_id if present (format: "name_uniq")
        uniq_key = None
        kbd_name = kbd_data.get('keyboard_name', 'Unknown')
        
        # Try to extract uniq from the ID
        if '_' in kbd_id and kbd_id != kbd_name:
            # Might have uniq in the ID
            parts = kbd_id.rsplit('_', 1)
            if len(parts) == 2:
                potential_uniq = parts[1]
                # Check if this looks like a uniq (not just part of the name)
                if len(potential_uniq) > 5 or ':' in potential_uniq:
                    uniq_key = potential_uniq
                    kbd_name = parts[0]
        
        if not uniq_key:
            uniq_key = f"no_uniq_{kbd_id}"
        
        if uniq_key not in keyboards_by_uniq:
            keyboards_by_uniq[uniq_key] = {
                'best_name': kbd_name,
                'unified_id': None,
                'mappings': {},
                'is_connected': False
            }
        
        # Merge mappings
        keyboards_by_uniq[uniq_key]['mappings'].update(kbd_data.get('custom_mappings', {}))
        
        # Update best name (prefer shorter, or one without "Keyboard" suffix)
        if len(kbd_name) < len(keyboards_by_uniq[uniq_key]['best_name']):
            keyboards_by_uniq[uniq_key]['best_name'] = kbd_name
        elif "Keyboard" not in kbd_name and "Keyboard" in keyboards_by_uniq[uniq_key]['best_name']:
            keyboards_by_uniq[uniq_key]['best_name'] = kbd_name
    
    # Now process detected keyboards
    detected = detect_keyboards()
    for kbd in detected:
        uniq_key = kbd.get('uniq') if kbd.get('uniq') else f"no_uniq_{kbd['name']}"
        kbd_name = kbd['name']
        
        if uniq_key not in keyboards_by_uniq:
            keyboards_by_uniq[uniq_key] = {
                'best_name': kbd_name,
                'unified_id': None,
                'mappings': {},
                'is_connected': True
            }
        else:
            keyboards_by_uniq[uniq_key]['is_connected'] = True
        
        # Update best name
        current_best = keyboards_by_uniq[uniq_key]['best_name']
        if len(kbd_name) < len(current_best):
            keyboards_by_uniq[uniq_key]['best_name'] = kbd_name
        elif "Keyboard" not in kbd_name and "Keyboard" in current_best:
            keyboards_by_uniq[uniq_key]['best_name'] = kbd_name
    
    # Create unified entries
    result = []
    for uniq_key, data in keyboards_by_uniq.items():
        best_name = data['best_name']
        if uniq_key.startswith("no_uniq_"):
            unified_id = best_name
        else:
            unified_id = f"{best_name}_{uniq_key}"
        
        result.append({
            'keyboard_id': unified_id,
            'keyboard_name': best_name,
            'mapping_count': len(data['mappings']),
            'is_connected': data['is_connected']
        })
    
    return jsonify(keyboards=result)

@app.route("/keyboard_mappings/<kbd_id>", methods=["GET"])
def get_keyboard_mappings_detail(kbd_id):
    """Get detailed mappings for a specific keyboard"""
    if kbd_id not in keyboard_mappings:
        # Create empty entry
        keyboard_mappings[kbd_id] = {
            'keyboard_name': 'Unknown',
            'custom_mappings': {}
        }
    
    kbd_data = keyboard_mappings[kbd_id]
    
    # Convert mappings to a more UI-friendly format
    mappings_list = []
    for code, mapping in kbd_data.get('custom_mappings', {}).items():
        # Get key name
        if EVDEV_AVAILABLE:
            key_name = ecodes.KEY.get(int(code), f"KEY_{code}")
        else:
            key_name = f"KEY_{code}"
        
        mappings_list.append({
            'code': int(code),
            'key_name': key_name,
            'type': mapping.get('type'),
            'hid_code': mapping.get('hid_code'),
            'text': mapping.get('text'),
            'description': get_mapping_description(mapping)
        })
    
    return jsonify(
        keyboard_id=kbd_id,
        keyboard_name=kbd_data.get('keyboard_name', 'Unknown'),
        mappings=mappings_list,
        count=len(mappings_list)
    )

def get_mapping_description(mapping):
    """Generate human-readable description of a mapping"""
    if mapping.get('type') == 'suppress':
        return "🚫 Suppressed (ignored)"
    elif mapping.get('type') == 'hid':
        hid_code = mapping.get('hid_code')
        return f"→ HID 0x{hid_code:02X}" if hid_code else "→ HID (unknown)"
    elif mapping.get('type') == 'text':
        text = mapping.get('text', '')
        preview = text[:20] + '...' if len(text) > 20 else text
        return f"→ Text: {preview}"
    return "Unknown"

@app.route("/keyboard_mappings/<kbd_id>/mapping", methods=["POST"])
def add_keyboard_mapping(kbd_id):
    """Add or update a mapping for a specific keyboard"""
    global keyboard_mappings
    
    data = request.json
    code = data.get('code')
    mapping_type = data.get('type')  # 'hid', 'text', or 'suppress'
    
    if code is None or not mapping_type:
        return jsonify(ok=False, error="code and type required"), 400
    
    # Ensure keyboard exists - try to get real name from detected keyboards
    if kbd_id not in keyboard_mappings:
        # Try to find the keyboard name from currently detected keyboards
        detected = detect_keyboards()
        kbd_name = 'Unknown'
        for kbd in detected:
            detected_id = f"{kbd['name']}_{kbd['uniq']}" if kbd['uniq'] else kbd['name']
            if detected_id == kbd_id:
                kbd_name = kbd['name']
                break
        
        keyboard_mappings[kbd_id] = {
            'keyboard_name': kbd_name,
            'custom_mappings': {}
        }
    else:
        # Update name if it's currently "Unknown" and we can detect it
        if keyboard_mappings[kbd_id].get('keyboard_name') == 'Unknown':
            detected = detect_keyboards()
            for kbd in detected:
                detected_id = f"{kbd['name']}_{kbd['uniq']}" if kbd['uniq'] else kbd['name']
                if detected_id == kbd_id:
                    keyboard_mappings[kbd_id]['keyboard_name'] = kbd['name']
                    break
    
    # Create mapping based on type
    if mapping_type == 'suppress':
        mapping = {'type': 'suppress'}
    elif mapping_type == 'hid':
        hid_code = data.get('hid_code')
        if not hid_code:
            return jsonify(ok=False, error="hid_code required for type=hid"), 400
        mapping = {'type': 'hid', 'hid_code': int(hid_code)}
    elif mapping_type == 'text':
        text = data.get('text')
        if not text:
            return jsonify(ok=False, error="text required for type=text"), 400
        mapping = {'type': 'text', 'text': text}
    else:
        return jsonify(ok=False, error="Invalid type"), 400
    
    keyboard_mappings[kbd_id]['custom_mappings'][code] = mapping
    save_keyboard_mappings(keyboard_mappings)
    
    return jsonify(ok=True, message=f"Mapping added for code {code}")

@app.route("/keyboard_mappings/<kbd_id>/mapping/<int:code>", methods=["DELETE"])
def delete_keyboard_mapping(kbd_id, code):
    """Delete a specific mapping"""
    global keyboard_mappings
    
    if kbd_id not in keyboard_mappings:
        return jsonify(ok=False, error="Keyboard not found"), 404
    
    mappings = keyboard_mappings[kbd_id].get('custom_mappings', {})
    if code in mappings:
        del mappings[code]
        save_keyboard_mappings(keyboard_mappings)
        return jsonify(ok=True, message=f"Mapping deleted for code {code}")
    
    return jsonify(ok=False, error="Mapping not found"), 404

@app.route("/keyboard_mappings/listen", methods=["POST", "GET", "DELETE"])
def keyboard_listen_mode():
    """Start/stop listening mode for key capture"""
    global listening_keyboard_id, captured_key_buffer
    
    if request.method == "GET":
        # Get current listening status
        with listening_lock:
            return jsonify({
                'listening': listening_keyboard_id is not None,
                'keyboard_id': listening_keyboard_id,
                'captured_keys': list(captured_key_buffer)
            })
    
    elif request.method == "DELETE":
        # Stop listening and clear buffer
        with listening_lock:
            listening_keyboard_id = None
            captured_key_buffer.clear()
        return jsonify(ok=True, message="Listening mode stopped")
    
    # POST - Start listening
    data = request.json or {}
    kbd_id = data.get('keyboard_id')
    
    if not kbd_id:
        return jsonify(ok=False, error="keyboard_id required"), 400
    
    # Verify keyboard exists
    if kbd_id not in keyboard_mappings:
        return jsonify(ok=False, error="Keyboard not found"), 404
    
    with listening_lock:
        listening_keyboard_id = kbd_id
        captured_key_buffer.clear()
    
    return jsonify(ok=True, message=f"Listening for keys on {keyboard_mappings[kbd_id]['keyboard_name']}")

@app.route("/keyboard_mappings/captured", methods=["GET", "DELETE"])
def get_captured_keys():
    """Get or clear captured keys"""
    global captured_key_buffer
    
    if request.method == "DELETE":
        with listening_lock:
            captured_key_buffer.clear()
        return jsonify(ok=True, message="Captured keys cleared")
    
    # GET - Return captured keys
    with listening_lock:
        keys = list(captured_key_buffer)
    return jsonify(keys=keys, count=len(keys))

@app.route("/emulation_profiles/export", methods=["GET"])
def export_emulation_profiles():
    """Export all emulation profiles"""
    return jsonify({
        'type': 'emulation_profiles',
        **emulation_profiles
    })

def main():
    """Entry point for keybird-server command"""
    global PASSTHROUGH_ENABLED, passthrough_thread, MOUSE_PASSTHROUGH_ENABLED, mouse_passthrough_thread
    
    # Auto-start pass-through modes on boot (always enabled regardless of previous state)
    if EVDEV_AVAILABLE:
        # Start keyboard pass-through
        print("🎹 Auto-starting keyboard pass-through mode...")
        PASSTHROUGH_ENABLED = True
        passthrough_thread = threading.Thread(target=pass_through_loop, daemon=True)
        passthrough_thread.start()
        print("✅ Keyboard pass-through mode active - physical keyboard ready!")
        
        # Start mouse pass-through
        print("🖱️  Auto-starting mouse pass-through mode...")
        MOUSE_PASSTHROUGH_ENABLED = True
        mouse_passthrough_thread = threading.Thread(target=mouse_pass_through_loop, daemon=True)
        mouse_passthrough_thread.start()
        print("✅ Mouse pass-through mode active - physical mouse ready!")
    
    print(f"🌐 Starting Keybird web server on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)

if __name__ == "__main__":
    main()


