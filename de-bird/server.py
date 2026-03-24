#!/usr/bin/env python3
# Pi Keyboard Bridge - Text to HID + Pass-through + Learning Mode

import time
import os
import threading
import select
import json
from collections import deque

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
PROFILES_FILE = "/opt/de-bird/keyboard_profiles.json"
MAPPINGS_FILE = "/opt/de-bird/keyboard_mappings.json"
CALIBRATIONS_FILE = "/opt/de-bird/trackpad_calibrations.json"

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
# CRITICAL: Initialize to True if evdev is available (pass-through should always be on by default)
PASSTHROUGH_ENABLED = EVDEV_AVAILABLE
passthrough_thread = None

MOUSE_PASSTHROUGH_ENABLED = EVDEV_AVAILABLE
mouse_passthrough_thread = None

LED_FORWARDING_ENABLED = EVDEV_AVAILABLE
led_forwarding_thread = None

# Current LED state from host (updated by LED forwarding thread)
led_state_lock = threading.Lock()
current_led_state = {
    'num_lock': False,
    'caps_lock': False,
    'scroll_lock': False,
    'raw': 0
}

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
            print("⚠️  No keyboards found for pass-through; waiting...", flush=True)
            time.sleep(3)
            if PASSTHROUGH_ENABLED:
                return pass_through_loop()
            return

        ks = KeyState()
        print(f"✅ Pass-through mode ACTIVE - monitoring {len(keyboards)} keyboard(s)", flush=True)

        # Retry loop for device availability - keep retrying forever while enabled
        while PASSTHROUGH_ENABLED:
            try:
                # Check if HID device exists before opening
                if not os.path.exists(HID_PATH):
                    print(f"⚠️  {HID_PATH} not available, waiting...", flush=True)
                    time.sleep(2)
                    continue

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
                                            modifiers = mapping.get('modifiers', 0)  # Get modifiers, default 0
                                            if hid_code:
                                                # Save current modifier state, then set mapping modifiers
                                                old_mod = ks.mod
                                                ks.mod = modifiers  # Set modifiers from mapping
                                                ks.press(hid_code)
                                                hid.write(ks.report())
                                                hid.flush()
                                                # Restore original modifier state after sending mapped key
                                                ks.mod = old_mod
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
                                                # Save current modifier state before release
                                                old_mod = ks.mod
                                                # Clear modifiers for release (HID protocol: release keys without modifiers)
                                                ks.mod = 0
                                                ks.release(hid_code)
                                                hid.write(ks.report())
                                                hid.flush()
                                                # Restore original modifier state after releasing mapped key
                                                ks.mod = old_mod
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

                # If we exit the with block normally, break the retry loop
                break

            except (OSError, IOError) as e:
                # Device error - might be temporary, keep retrying while enabled
                errno = getattr(e, 'errno', None)
                if errno == 19:  # No such device
                    print(f"⚠️  HID device temporarily unavailable: {e}, retrying...", flush=True)
                else:
                    print(f"⚠️  Pass-through I/O error: {e}, retrying...", flush=True)
                time.sleep(2)
                continue
            except Exception as e:
                print(f"❌ Pass-through error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                break

        # If still enabled, restart the loop
        if PASSTHROUGH_ENABLED:
            print("🔄 Restarting pass-through loop...", flush=True)
            time.sleep(2)
            return pass_through_loop()

        print("⏹️  Pass-through mode STOPPED", flush=True)

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

        # Retry loop for device availability - keep retrying forever while enabled
        while MOUSE_PASSTHROUGH_ENABLED:
            try:
                # Check if HID mouse device exists before opening
                if not os.path.exists(HID_MOUSE_PATH):
                    print(f"⚠️  {HID_MOUSE_PATH} not available, waiting...", flush=True)
                    time.sleep(2)
                    continue

                with open(HID_MOUSE_PATH, "wb", buffering=0) as hid_mouse:
                    # Accumulation variables for movement coalescing
                    dx_total = 0
                    dy_total = 0
                    wheel_total = 0

                    def _flush_mouse_movement():
                        """Flush accumulated movement values to HID device"""
                        nonlocal dx_total, dy_total, wheel_total

                        # Clamp to int8 range (-127 to 127)
                        dx_sent = max(-127, min(127, dx_total))
                        dy_sent = max(-127, min(127, dy_total))
                        wheel_sent = max(-127, min(127, wheel_total))

                        # Only send if there's movement to send
                        if dx_sent == 0 and dy_sent == 0 and wheel_sent == 0:
                            return

                        # Convert to unsigned bytes
                        dx_byte = dx_sent if dx_sent >= 0 else (256 + dx_sent)
                        dy_byte = dy_sent if dy_sent >= 0 else (256 + dy_sent)
                        wheel_byte = wheel_sent if wheel_sent >= 0 else (256 + wheel_sent)

                        # Send report
                        report = bytes([buttons_state, dx_byte, dy_byte, wheel_byte])
                        hid_mouse.write(report)
                        hid_mouse.flush()

                        # Keep remainder (for overflow handling)
                        dx_total -= dx_sent
                        dy_total -= dy_sent
                        wheel_total -= wheel_sent

                    while MOUSE_PASSTHROUGH_ENABLED:
                        # Monitor all mouse file descriptors
                        fds = [m.fd for m in mice]
                        r, _, _ = select.select(fds, [], [], 0.001)
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
                                    # Flush accumulated movements before button state change
                                    _flush_mouse_movement()

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

                                    # Send button state change immediately (with zero movement)
                                    report = bytes([buttons_state, 0, 0, 0])
                                    hid_mouse.write(report)
                                    hid_mouse.flush()

                                # Handle movement events
                                elif ev.type == ecodes.EV_REL:
                                    # Accumulate movement values (don't clamp yet - need full value for calibration)
                                    if ev.code == ecodes.REL_X:
                                        dx_total += ev.value
                                        # Track position for calibration (use full ev.value, not clamped)
                                        with calibration_lock:
                                            calibration_state['current_x'] += ev.value
                                    elif ev.code == ecodes.REL_Y:
                                        dy_total += ev.value
                                        # Track position for calibration (use full ev.value, not clamped)
                                        with calibration_lock:
                                            calibration_state['current_y'] += ev.value
                                    elif ev.code == ecodes.REL_WHEEL:
                                        wheel_total += ev.value

                            # After processing all events from this device, flush any accumulated movements
                            _flush_mouse_movement()

                # If we exit the with block normally, break the retry loop
                break

            except (OSError, IOError) as e:
                # Device error - might be temporary, keep retrying while enabled
                errno = getattr(e, 'errno', None)
                if errno == 19:  # No such device
                    print(f"⚠️  HID mouse device temporarily unavailable: {e}, retrying...", flush=True)
                else:
                    print(f"⚠️  Mouse pass-through I/O error: {e}, retrying...", flush=True)
                time.sleep(2)
                continue
            except Exception as e:
                print(f"❌ Mouse pass-through error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                break

        # If still enabled, restart the loop
        if MOUSE_PASSTHROUGH_ENABLED:
            print("🔄 Restarting mouse pass-through loop...", flush=True)
            time.sleep(2)
            return mouse_pass_through_loop()

        print("⏹️  Mouse pass-through mode STOPPED", flush=True)

    # LED forwarding function - reads LED state from host and forwards to physical keyboards
    def led_forwarding_loop():
        """Read LED output reports from /dev/hidg0 and forward to physical keyboards"""
        global LED_FORWARDING_ENABLED, current_led_state

        if not EVDEV_AVAILABLE:
            return

        import fcntl

        print("💡 LED forwarding: Waiting for /dev/hidg0...", flush=True)

        # Wait for HID device to be available
        max_wait = 30
        waited = 0
        while not os.path.exists(HID_PATH) and waited < max_wait:
            time.sleep(1)
            waited += 1
            if not LED_FORWARDING_ENABLED:
                return

        if not os.path.exists(HID_PATH):
            print(f"⚠️  LED forwarding: {HID_PATH} not available after {max_wait}s", flush=True)
            return

        print(f"💡 LED forwarding: Reading from {HID_PATH}", flush=True)

        # Track last LED state to avoid redundant writes
        last_led_state = None

        # Cache of keyboard devices that support LEDs
        # Refresh this list periodically in case devices are plugged/unplugged
        led_keyboards = []  # List of (InputDevice, led_caps)
        last_scan_time = 0
        scan_interval = 30  # Rescan for keyboards every 30 seconds

        def scan_led_keyboards():
            """Scan for keyboards that support LED output"""
            keyboards = []
            for path in glob.glob("/dev/input/event*"):
                try:
                    dev = InputDevice(path)
                    caps = dev.capabilities()

                    # Check if it's a keyboard (has KEY_A and KEY_ENTER)
                    key_caps = caps.get(ecodes.EV_KEY, [])
                    if ecodes.KEY_A not in key_caps or ecodes.KEY_ENTER not in key_caps:
                        continue

                    # Check if keyboard supports LED output
                    led_caps = caps.get(ecodes.EV_LED, [])
                    if led_caps:
                        keyboards.append((dev, led_caps))
                except (OSError, PermissionError):
                    # Device might not be accessible
                    continue
                except Exception:
                    # Skip devices that cause errors
                    continue
            return keyboards

        # Initial scan
        led_keyboards = scan_led_keyboards()
        print(f"💡 Found {len(led_keyboards)} keyboard(s) with LED support", flush=True)

        try:
            with open(HID_PATH, "rb", buffering=0) as hid:
                # Set non-blocking mode
                flags = fcntl.fcntl(hid.fileno(), fcntl.F_GETFL)
                fcntl.fcntl(hid.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

                while LED_FORWARDING_ENABLED:
                    # Periodically rescan for keyboards in case devices are plugged/unplugged
                    current_time = time.time()
                    if current_time - last_scan_time > scan_interval:
                        led_keyboards = scan_led_keyboards()
                        last_scan_time = current_time

                    try:
                        # Read 1-byte LED output report from host
                        # The host sends this when Caps Lock, Num Lock, or Scroll Lock state changes
                        led_byte = hid.read(1)

                        if not led_byte or len(led_byte) == 0:
                            # No data available, wait a bit
                            time.sleep(0.1)
                            continue

                        led_state = led_byte[0]

                        # Only process if LED state changed
                        if led_state == last_led_state:
                            continue

                        last_led_state = led_state

                        # Parse LED bits:
                        # Bit 0 = Num Lock
                        # Bit 1 = Caps Lock
                        # Bit 2 = Scroll Lock
                        num_lock = bool(led_state & 0x01)
                        caps_lock = bool(led_state & 0x02)
                        scroll_lock = bool(led_state & 0x04)

                        # Update global LED state for API access
                        with led_state_lock:
                            current_led_state = {
                                'num_lock': num_lock,
                                'caps_lock': caps_lock,
                                'scroll_lock': scroll_lock,
                                'raw': led_state
                            }

                        print(f"💡 LED state from host: Num={num_lock} Caps={caps_lock} Scroll={scroll_lock} (0x{led_state:02x})", flush=True)

                        # Forward LED state to all cached keyboards
                        keyboards_updated = 0
                        for dev, led_caps in led_keyboards:
                            try:
                                # Write LED events to physical keyboard
                                # evdev.write(type, code, value) where value is 0 or 1
                                if ecodes.LED_NUML in led_caps:
                                    dev.write(ecodes.EV_LED, ecodes.LED_NUML, 1 if num_lock else 0)
                                if ecodes.LED_CAPSL in led_caps:
                                    dev.write(ecodes.EV_LED, ecodes.LED_CAPSL, 1 if caps_lock else 0)
                                if ecodes.LED_SCROLLL in led_caps:
                                    dev.write(ecodes.EV_LED, ecodes.LED_SCROLLL, 1 if scroll_lock else 0)

                                keyboards_updated += 1

                            except (OSError, PermissionError):
                                # Device might have been unplugged or permissions changed
                                continue
                            except Exception as e:
                                # Skip devices that cause errors
                                continue

                        if keyboards_updated > 0:
                            print(f"💡 Forwarded LED state to {keyboards_updated} keyboard(s)", flush=True)

                    except BlockingIOError:
                        # No data available, continue
                        time.sleep(0.1)
                        continue
                    except Exception as e:
                        print(f"⚠️  LED forwarding read error: {e}", flush=True)
                        time.sleep(0.5)
                        continue

        except Exception as e:
            print(f"❌ LED forwarding error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            print("⏹️  LED forwarding STOPPED", flush=True)

# --------------- Web UI --------------------------

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

def main():
    """Entry point for de-bird-server command"""
    global PASSTHROUGH_ENABLED, passthrough_thread, MOUSE_PASSTHROUGH_ENABLED, mouse_passthrough_thread
    global LED_FORWARDING_ENABLED, led_forwarding_thread

    # CRITICAL: Always enable pass-through flags FIRST, before starting threads
    # This ensures the API endpoints return the correct state even if threads fail to start
    if EVDEV_AVAILABLE:
        PASSTHROUGH_ENABLED = True
        MOUSE_PASSTHROUGH_ENABLED = True
        LED_FORWARDING_ENABLED = True

    # Auto-start pass-through modes on boot (always enabled regardless of previous state)
    if EVDEV_AVAILABLE:
        # Start LED forwarding (forwards host LED state to physical keyboards)
        print("Starting LED forwarding...", flush=True)
        led_forwarding_thread = threading.Thread(target=led_forwarding_loop, daemon=True)
        led_forwarding_thread.start()
        print("LED forwarding active - host LED state will sync to physical keyboards!", flush=True)

        # Start mouse pass-through
        print("Starting mouse pass-through mode...", flush=True)
        mouse_passthrough_thread = threading.Thread(target=mouse_pass_through_loop, daemon=True)
        mouse_passthrough_thread.start()
        print("Mouse pass-through mode active - physical mouse ready!", flush=True)

        # Start keyboard pass-through
        print("Starting keyboard pass-through mode...", flush=True)
        pass_through_loop()

    else:
        print("evdev not available, functionality does not work", flush=True)
        os._exit(1)

if __name__ == "__main__":
    main()

