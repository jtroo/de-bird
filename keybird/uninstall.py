#!/usr/bin/env python3
"""
Keybird Uninstall - Clean removal of system configuration

This script removes all system-level changes made by keybird-setup:
- USB gadget configuration
- Systemd services
- Boot configuration changes
- Installed files
"""

import os
import sys
import subprocess
from pathlib import Path

def check_privileges():
    """Ensure script is run with sudo/root"""
    if os.geteuid() != 0:
        print("❌ Error: This script must be run with sudo")
        print("   Usage: sudo keybird-uninstall")
        sys.exit(1)

def confirm_uninstall():
    """Ask user to confirm uninstall"""
    print("⚠️  WARNING: This will remove all Keybird system configuration")
    print()
    print("   The following will be removed:")
    print("   - USB gadget configuration (boot files)")
    print("   - Systemd services")
    print("   - Installed scripts in /opt/keybird/")
    print("   - HID device setup")
    print()
    print("   Your saved profiles and mappings will be kept:")
    print("   - /home/pi/keyboard_profiles.json")
    print("   - /home/pi/keyboard_mappings.json")
    print("   - /home/pi/trackpad_calibrations.json")
    print()
    
    response = input("   Continue with uninstall? (yes/NO): ")
    if response.lower() != 'yes':
        print("   Uninstall cancelled.")
        sys.exit(0)

def stop_services():
    """Stop and disable systemd services"""
    print("🛑 Stopping and disabling services...")
    
    services = ['pi-hid-bridge.service', 'hid-gadget.service']
    for service in services:
        try:
            subprocess.run(['systemctl', 'stop', service], check=False, 
                         stderr=subprocess.DEVNULL)
            subprocess.run(['systemctl', 'disable', service], check=False,
                         stderr=subprocess.DEVNULL)
            print(f"   ✓ Stopped and disabled {service}")
        except:
            pass

def remove_systemd_services():
    """Remove systemd service files"""
    print("🗑️  Removing systemd service files...")
    
    service_files = [
        '/etc/systemd/system/hid-gadget.service',
        '/etc/systemd/system/pi-hid-bridge.service'
    ]
    
    for service in service_files:
        if os.path.exists(service):
            os.remove(service)
            print(f"   ✓ Removed {service}")
    
    subprocess.run(['systemctl', 'daemon-reload'], check=False)

def cleanup_usb_gadget():
    """Remove USB gadget configuration"""
    print("🔌 Cleaning up USB gadget...")
    
    cleanup_script = '/opt/keybird/scripts/cleanup_gadget.sh'
    if os.path.exists(cleanup_script):
        try:
            subprocess.run(['bash', cleanup_script], check=False,
                         stderr=subprocess.DEVNULL)
            print("   ✓ USB gadget removed")
        except:
            pass

def remove_boot_config():
    """Remove USB gadget configuration from boot files"""
    print("⚙️  Removing boot configuration...")
    
    # Find and update config.txt
    config_paths = ['/boot/firmware/config.txt', '/boot/config.txt']
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    lines = f.readlines()
                
                # Remove dwc2 overlay lines
                new_lines = [line for line in lines if 'dtoverlay=dwc2' not in line]
                
                if len(new_lines) < len(lines):
                    with open(config_path, 'w') as f:
                        f.writelines(new_lines)
                    print(f"   ✓ Removed dwc2 overlay from {config_path}")
                    
                    # Restore from backup if exists
                    backup = f"{config_path}.backup"
                    if os.path.exists(backup):
                        print(f"   💡 Backup available at {backup}")
            except Exception as e:
                print(f"   ⚠️  Could not modify {config_path}: {e}")
    
    # Find and update cmdline.txt
    cmdline_paths = ['/boot/firmware/cmdline.txt', '/boot/cmdline.txt']
    for cmdline_path in cmdline_paths:
        if os.path.exists(cmdline_path):
            try:
                with open(cmdline_path, 'r') as f:
                    cmdline = f.read()
                
                # Remove modules-load parameter
                if 'modules-load=dwc2' in cmdline:
                    cmdline = cmdline.replace(' modules-load=dwc2,g_hid', '')
                    cmdline = cmdline.replace(' modules-load=dwc2', '')
                    
                    with open(cmdline_path, 'w') as f:
                        f.write(cmdline)
                    print(f"   ✓ Removed modules-load from {cmdline_path}")
            except Exception as e:
                print(f"   ⚠️  Could not modify {cmdline_path}: {e}")

def remove_installed_files():
    """Remove installed files from /opt/keybird/"""
    print("📁 Removing installed files...")
    
    install_dir = Path('/opt/keybird')
    if install_dir.exists():
        import shutil
        shutil.rmtree(install_dir)
        print("   ✓ Removed /opt/keybird/")

def main():
    """Main uninstall function"""
    print("🗑️  Keybird Uninstall")
    print("=" * 60)
    print()
    
    check_privileges()
    confirm_uninstall()
    
    print()
    stop_services()
    cleanup_usb_gadget()
    remove_systemd_services()
    remove_boot_config()
    remove_installed_files()
    
    print()
    print("=" * 60)
    print("✅ Keybird system configuration removed!")
    print()
    print("📋 To complete uninstall:")
    print()
    print("   1. Uninstall Python package:")
    print("      sudo pip uninstall keybird")
    print()
    print("   2. (Optional) Remove saved data:")
    print("      rm /home/pi/keyboard_profiles.json")
    print("      rm /home/pi/keyboard_mappings.json")
    print("      rm /home/pi/trackpad_calibrations.json")
    print()
    print("   3. Reboot to apply boot config changes:")
    print("      sudo reboot")
    print()
    print("💡 Tip: Your profiles and mappings were kept in case you reinstall.")
    print()

if __name__ == '__main__':
    main()

