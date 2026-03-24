# Keybird Release Notes

Complete changelog of all releases with dates, commit hashes, and detailed changes.

---

## v1.0.12 - December 28, 2025

**Commit:** `d42297c`

**Pass-Through Initialization Fix**

- Fixed pass-through flags initialization at module level (`EVDEV_AVAILABLE`)
  - Ensures flags are `True` from the start, not just when `main()` runs
- Improved deployment script to prefer source files during development
  - Allows deploying uncommitted changes from source directory
- Ensures GUI correctly shows pass-through status on startup

---

## v1.0.11 - December 27, 2025

**Commit:** `e2d2629` (version bump), `334928a` (changes)

**Pass-Through Reliability & Key Mapping Fixes**

- Fixed pass-through always enabled on boot
  - Set pass-through flags (`PASSTHROUGH_ENABLED`, `MOUSE_PASSTHROUGH_ENABLED`) to `True` at start of `main()` before starting threads
  - Added global statements to `main()` to properly modify global flags
  - Removed `max_retries` limit - pass-through loops now retry forever while enabled
- Fixed key mapping modifier handling
  - Preserve user's modifier state when processing mapped keys
- Fixed indentation error in mouse pass-through loop
- Improved mouse polling rate (reduced select timeout from 0.5s to 0.001s)

**Related commits:**
- `383c6d7` (Dec 28) - Implement mouse movement coalescing optimization
  - Added movement event coalescing to batch multiple REL_X/REL_Y/REL_WHEEL events
  - Reduce USB traffic by batching movements into fewer HID reports
  - Maintain zero-latency button response (flush movements before button events)
  - Preserve calibration tracking with full ev.value (not clamped)
  - Handle overflow smoothly by preserving remainder values
  - Maintain multi-mouse support and all existing functionality

---

## v1.0.10 - December 12, 2025

**Commit:** `d04f48e`

**Auto-Start & UI Fixes**

- Pass-through modes (keyboard and mouse) now auto-start on boot by default
- UI toggles correctly reflect enabled state
- Restored missing LED indicators and controls on Control tab

---

## v1.0.9 - December 11, 2025

**Commit:** `0e8c5e3`, `bc1ae8d`

**Human-Readable HID Code Dropdown**

- Added dropdown with human-readable key names (Delete, Enter, F1-F24, etc.) instead of requiring hex codes
- Shows format: 'Delete (0x4C)' for easy selection
- Custom option allows typing hex codes for unknown keys
- Automatically shows dropdown or custom input based on existing value

**Related commits:**
- `ddc9ad2` - Fix: Move listen buttons outside input-group for proper display
- `9115e64` - Add CSS styling for modifier checkboxes in mappings table
- `4c9b04b` - Fix: Make listen button always visible, improve checkbox visibility

---

## v1.0.8 - December 11, 2025

**Commit:** `7e448c1`, `cc4198a`

**Revert to File-Copying Deployment**

- Restored original deployment approach for better workflow
- Systemd service uses `/opt/de-bird/pi-hid-bridge/pi_kb.py`
- Maintains workflow: edit locally, deploy to multiple Pis
- No pip install needed on Pi, works with fresh SD cards

---

## v1.0.7 - December 11, 2025

**Commit:** `8b88825`, `cd5a1a0`

**Editable Mappings & Modifier Support**

- Auto-inject captured keys into table (no prompt dialog)
- Make all table rows editable with inline inputs
- Add modifier support (Ctrl, Alt, Shift, Win) for key combinations
- Add PUT endpoint for updating mappings
- Update HID handler to support modifiers
- Enable mapping keys to combinations like Ctrl+Alt+Del

---

## v1.0.6 - November 21, 2025

**Commit:** `c483823`

**LED Control & Robustness**

- LED forwarding: Host lock key state syncs to physical keyboards
- Real-time LED status indicators in Control tab
- Clickable lock key toggles (Num/Caps/Scroll Lock) from GUI
- Improved pass-through crash recovery with auto-restart
- Updated HID descriptor to include LED output reports
- Enhanced UI with hover effects and visual feedback

**Related commits:**
- `5cbfe0a` (Nov 20) - Add LED forwarding: sync host LED state (Caps/Num/Scroll Lock) to physical keyboards
- `8a80952` (Nov 20) - Add real-time LED status indicators in Control tab
- `f5257d6` (Nov 20) - Fix pass-through crash recovery and improve robustness
- `7a1982f` (Nov 20) - Make LED indicators clickable to toggle lock keys from GUI

---

## v1.0.5 - November 12, 2025

**Commit:** `51d0f0e`

**Listen Mode & Branding**

- Added key listening mode for easy keyboard mapping (press key to capture code)
- Auto-start keyboard and mouse pass-through on boot (always enabled)
- Fixed keyboard deduplication (merge multiple interfaces of same device)
- Integrated favicons and app icons for all platforms
- Rebranded to 'Keybird' with updated navbar and page title
- Fixed text mapping to actually send keystrokes (not just log)
- Improved mapping count display in keyboard list

**Related commits:**
- `800b17a` (Nov 12) - Include favicon files in package distribution

---

## v1.0.4 - October 25, 2025

**Commit:** `b7b6263`

**PyPI Fix**

- Corrected package build to include touch support for iPhone/iPad trackpad

---

## v1.0.3 - October 24, 2025

**Commit:** `2a263b8`

**Mobile Support**

- Added touch support for iPhone/iPad trackpad
  - Touch to move cursor
  - Tap to click
  - Two-finger right-click
- Prevented default touch behaviors (scrolling, zooming)
- Added mobile-specific CSS for better touch targets
- Updated version to 1.0.3 and published to PyPI

---

## v1.0.2 - October 24, 2025

**Commit:** `f57531a`

**Modernization**

- Updated Python version requirement from >=3.7 to >=3.10
- Replaced deprecated `pkg_resources` with `importlib.resources`
- Updated `deploy_cli.py` to use modern resource access APIs
- Updated PyPI classifiers to reflect Python 3.10+ support
- Fixed `ModuleNotFoundError: No module named 'pkg_resources'` issue

Resolves GitHub issue with Python 3.12 compatibility.

---

## v1.0.1 - October 24, 2025

**Commit:** `e9baea5`

**Bug Fix**

- Fixed silent crash in keyboard pass-through mode
- Fixed `BlockingIOError` when reading from keyboard devices
- Added non-blocking mode for keyboard input devices using fcntl
- Added proper exception handling for `BlockingIOError`
- Improved error logging with traceback for debugging

Resolves issue where pass-through thread would silently exit, preventing keyboard input from being forwarded to target computer.

---

## v1.0.0 - October 17, 2025

**Commit:** `6e4216a`

**Initial Release**

- Keyboard pass-through (multi-keyboard support)
- Web UI with Bootstrap 5 dark theme
- Mouse control
- Trackpad calibration
- Multi-keyboard support
- Emulation profiles
- Per-keyboard mappings
- YubiKey support

---

## v0.1 - October 2025

**Initial Prototype**

Initial development and proof-of-concept release.
