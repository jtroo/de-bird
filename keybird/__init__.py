"""
Keybird - USB HID Keyboard/Mouse Bridge for Raspberry Pi

Turn a Raspberry Pi into a USB HID device with web-based control,
multi-keyboard passthrough, and custom key mapping.

GitHub: https://github.com/mcyork/keybird
"""

__version__ = "2.1.0"
__author__ = "Ian McCutcheon"
__license__ = "MIT"

# Lazy import to avoid Pi-specific initialization when importing package
def create_app():
    from keybird.server import create_app as _create_app
    return _create_app()

__all__ = ['create_app', '__version__']

