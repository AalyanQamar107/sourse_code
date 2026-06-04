"""
Linux USB Collector - Fixed all critical bugs
"""
import os
import subprocess
import re
from datetime import datetime
from ..base_collector import BaseCollector

class LinuxUSBCollector(BaseCollector):

    KEYS = [
        'device_name', 'device_id', 'connection_type', 'last_connected',
        'serial_number', 'vendor', 'product_id', 'speed',
        'mount_point', 'connect_date',
    ]

    def collect(self):
        devices = []
        devices.extend(self._lsusb())
        devices.extend(self._storage())
        devices.extend(self._mount_history())

        # Fix #5: clean deduplication without walrus operator
        seen   = set()
        unique = []
        for d in devices:
            key = d.get('device_id') or d.get('device_name', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(d)
        return unique

    # ------------------------------------------------------------------ helpers
    def _make_dict(self, **kwargs):
        d = {k: '' for k in self.KEYS}
        for k, v in kwargs.items():
            d[k] = str(v)[:200] if isinstance(v, str) else (v or '')
        # Always derive connect_date from last_connected
        lc = d.get('last_connected', '')
        d['connect_date'] = lc[:10] if lc else datetime.now().strftime('%Y-%m-%d')
        return d

    # ------------------------------------------------------------------ lsusb
    def _lsusb(self):
        """
        Fix #3: correct lsusb field parsing.
        lsusb line format:
          Bus 001 Device 002: ID 0781:5581 SanDisk Corp. Ultra
          [0]  [1] [2]    [3] [4][5]        [6+]
        """
        devices = []
        try:
            result = subprocess.run(
                ['lsusb'], capture_output=True, text=True, timeout=8
            )
            if result.returncode != 0:
                return devices

            now = datetime.now().isoformat()[:19]
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                # Need at least: Bus NNN Device NNN: ID VID:PID
                if len(parts) < 6:
                    continue

                vid_pid    = parts[5]                          # e.g. '0781:5581'
                vendor_id  = vid_pid.split(':')[0] if ':' in vid_pid else ''
                product_id = vid_pid.split(':')[1] if ':' in vid_pid else ''
                name       = ' '.join(parts[6:]).strip() if len(parts) > 6 else 'USB Device'
                if not name:
                    name = 'USB Device'

                bus    = parts[1]  # '001'
                dev_no = parts[3].rstrip(':')  # '002'
                dev_id = f"bus{bus}_dev{dev_no}_{vid_pid}"

                devices.append(self._make_dict(
                    device_name     = name,
                    device_id       = dev_id,
                    connection_type = 'External USB',
                    last_connected  = now,
                    vendor          = vendor_id,
                    product_id      = product_id,
                ))
        except FileNotFoundError:
            print("lsusb not found – skipping")
        except Exception as e:
            print(f"lsusb error: {e}")
        return devices

    # ------------------------------------------------------------------ storage
    def _storage(self):
        """Collect USB storage devices via sysfs and lsblk."""
        devices = []
        now = datetime.now().isoformat()[:19]

        # sysfs
        try:
            base = '/sys/bus/usb/devices'
            for dev in os.listdir(base):
                dev_path  = os.path.join(base, dev)
                iface     = os.path.join(dev_path, 'bInterfaceClass')
                if not os.path.exists(iface):
                    continue
                try:
                    with open(iface) as f:
                        cls = f.read().strip()
                except OSError:
                    continue
                if cls != '08':          # 08 = Mass Storage
                    continue

                name   = dev
                serial = ''
                product_file = os.path.join(dev_path, 'product')
                serial_file  = os.path.join(dev_path, 'serial')
                try:
                    with open(product_file) as f:
                        name = f.read().strip()
                except OSError:
                    pass
                try:
                    with open(serial_file) as f:
                        serial = f.read().strip()
                except OSError:
                    pass

                devices.append(self._make_dict(
                    device_name     = name,
                    device_id       = dev,
                    connection_type = 'External USB Storage',
                    last_connected  = now,
                    serial_number   = serial,
                ))
        except Exception as e:
            print(f"sysfs USB error: {e}")

        # lsblk
        try:
            result = subprocess.run(
                ['lsblk', '-o', 'NAME,TRAN,MODEL,SIZE,MOUNTPOINT', '-l', '-n'],
                capture_output=True, text=True, timeout=8
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if 'usb' not in line.lower():
                        continue
                    parts = line.split()
                    # NAME TRAN MODEL SIZE [MOUNTPOINT]
                    blk_name   = parts[0] if len(parts) > 0 else ''
                    model      = parts[2] if len(parts) > 2 else ''
                    size       = parts[3] if len(parts) > 3 else ''
                    mountpoint = parts[4] if len(parts) > 4 else ''
                    name       = f"{model} ({size})".strip() if model else blk_name
                    devices.append(self._make_dict(
                        device_name     = name or blk_name,
                        device_id       = blk_name,
                        connection_type = 'External USB Storage',
                        last_connected  = now,
                        mount_point     = mountpoint,
                    ))
        except FileNotFoundError:
            print("lsblk not found – skipping")
        except Exception as e:
            print(f"lsblk error: {e}")

        return devices

    # ------------------------------------------------------------------ history
    def _mount_history(self):
        """
        Fix #4: regex returns match object – extract group(1) properly.
        Collect USB history from dmesg and /proc/mounts.
        """
        devices = []
        now = datetime.now().isoformat()[:19]

        # dmesg
        try:
            result = subprocess.run(
                "dmesg -T 2>/dev/null | grep -iE 'usb|mass storage'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if 'New USB device' not in line and 'Mass Storage' not in line:
                        continue

                    # Fix #4: extract string from match object
                    m    = re.search(r'product:\s*([^\s,]+)', line, re.IGNORECASE)
                    name = m.group(1) if m else 'USB Device'

                    devices.append(self._make_dict(
                        device_name     = name,
                        device_id       = '',
                        connection_type = 'External USB (History)',
                        last_connected  = now,
                    ))
        except Exception as e:
            print(f"dmesg error: {e}")

        # /proc/mounts
        try:
            with open('/proc/mounts') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    dev, mp = parts[0], parts[1]
                    if not (dev.startswith('/dev/sd') or dev.startswith('/dev/mmcblk')):
                        continue
                    devices.append(self._make_dict(
                        device_name     = f"Mounted {os.path.basename(dev)}",
                        device_id       = dev,
                        connection_type = 'External USB Storage (Mounted)',
                        last_connected  = now,
                        mount_point     = mp,
                    ))
        except Exception as e:
            print(f"/proc/mounts error: {e}")

        return devices