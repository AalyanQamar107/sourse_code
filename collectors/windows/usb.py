"""
USB device collector for Windows - collects external storage devices and USB history.
"""
import os
import subprocess
import json
import winreg
from datetime import datetime, timedelta
from ..base_collector import BaseCollector

class USBCollector(BaseCollector):

    def collect(self):
        devices = []
        devices.extend(self._get_usb_storage_devices())
        devices.extend(self._get_current_usb_devices())
        devices.extend(self._get_usb_history())

        seen = set()
        unique = []
        for d in devices:
            did = d.get('device_id', '')
            if did not in seen:
                seen.add(did)
                unique.append(d)
        return unique

    def _get_usb_storage_devices(self):
        devices = []
        try:
            ps_command = '''
            Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR\\*\\*" -ErrorAction SilentlyContinue |
            Select-Object FriendlyName, ContainerID, Mfg, Service |
            ConvertTo-Json -Compress
            '''
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_command],
                capture_output=True, text=True, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW   # <-- hide PowerShell
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]

                now = datetime.now()
                for entry in data:
                    name = entry.get('FriendlyName', 'USB Storage Device')
                    if name and ';' in str(name):
                        name = name.split(';')[-1].strip()

                    devices.append({
                        'device_name':     str(name)[:200],
                        'device_id':       str(entry.get('ContainerID', ''))[:100],
                        'connection_type': 'External USB Storage',
                        'last_connected':  now.isoformat()[:19],
                        'serial_number':   '',
                        'vendor':          str(entry.get('Mfg', 'Unknown'))[:50],
                        'product_id':      '',
                        'speed':           '',
                        'mount_point':     '',
                        'connect_date':    now.strftime('%Y-%m-%d'),
                    })
        except Exception as e:
            print(f"USB storage error: {e}")
        return devices

    def _get_current_usb_devices(self):
        devices = []
        try:
            ps_command = '''
            Get-PnpDevice -Class USB -ErrorAction SilentlyContinue |
            Where-Object {$_.FriendlyName -notlike "*Root Hub*" -and $_.FriendlyName -notlike "*Host Controller*"} |
            Select-Object FriendlyName, InstanceId, Status, Class |
            ConvertTo-Json -Compress
            '''
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_command],
                capture_output=True, text=True, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW   # <-- hide PowerShell
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]

                now = datetime.now()
                for entry in data[:50]:
                    name = str(entry.get('FriendlyName', 'USB Device'))
                    if len(name) > 3:
                        name_lower = name.lower()
                        if any(x in name_lower for x in ['hub', 'controller', 'root']):
                            conn = 'Internal USB'
                        else:
                            conn = 'External USB'

                        devices.append({
                            'device_name':     name[:200],
                            'device_id':       str(entry.get('InstanceId', ''))[:100],
                            'connection_type': conn,
                            'last_connected':  now.isoformat()[:19],
                            'serial_number':   '',
                            'vendor':          '',
                            'product_id':      '',
                            'speed':           '',
                            'mount_point':     '',
                            'connect_date':    now.strftime('%Y-%m-%d'),
                        })
        except Exception as e:
            print(f"USB current devices error: {e}")
        return devices

    def _get_usb_history(self):
        devices = []
        try:
            # Use raw string to avoid Unicode escape issues
            key_path = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as usbstor_key:
                idx = 0
                while True:
                    try:
                        vendor_product   = winreg.EnumKey(usbstor_key, idx)
                        vendor_key_path  = f"{key_path}\\{vendor_product}"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, vendor_key_path) as vp_key:
                            dev_idx = 0
                            while True:
                                try:
                                    instance_id      = winreg.EnumKey(vp_key, dev_idx)
                                    device_key_path  = f"{vendor_key_path}\\{instance_id}"
                                    info = self._get_device_info(device_key_path, instance_id)
                                    if info:
                                        devices.append(info)
                                    dev_idx += 1
                                except OSError:
                                    break
                        idx += 1
                    except OSError:
                        break
        except Exception as e:
            print(f"USB history error: {e}")
        return devices

    def _get_device_info(self, key_path, instance_id):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as dev_key:
                try:
                    friendly_name, _ = winreg.QueryValueEx(dev_key, "FriendlyName")
                except FileNotFoundError:
                    friendly_name = instance_id

                key_info      = winreg.QueryInfoKey(dev_key)
                filetime_100ns = key_info[2]
                try:
                    last_seen = datetime(1601, 1, 1) + timedelta(
                        microseconds=filetime_100ns // 10
                    )
                except (OverflowError, OSError, ValueError):
                    last_seen = datetime.now()

                if not self.is_recent(last_seen):
                    return None

                return {
                    'device_name':     str(friendly_name)[:200] if friendly_name else 'Unknown',
                    'device_id':       instance_id[:200],
                    'connection_type': 'External USB Storage (History)',
                    'last_connected':  last_seen.isoformat()[:19],
                    'serial_number':   '',
                    'vendor':          '',
                    'product_id':      '',
                    'speed':           '',
                    'mount_point':     '',
                    'connect_date':    last_seen.strftime('%Y-%m-%d'),
                }
        except Exception as e:
            print(f"Error reading device {key_path}: {e}")
            return None