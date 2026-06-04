"""
System log and recent file collector for Linux.
"""
import os
import subprocess
from datetime import datetime
from ..base_collector import BaseCollector
from .usb import LinuxUSBCollector

class LinuxSystemCollector(BaseCollector):
    """
    Collects system logs (journalctl) and recently accessed files.
    """

    def collect(self):
        usb_collector = LinuxUSBCollector()
        usb_devices   = usb_collector.collect()
        return {
            'system_logs':  self._logs(),
            'usb_devices':  usb_devices,
            'recent_files': self._recent(),
        }

    def _logs(self):
        """
        Retrieve recent system logs using journalctl.
        Fix #6: parse real timestamp from each log line instead of using now().
        """
        logs = []
        try:
            result = subprocess.run(
                ['journalctl',
                 f'--since={self.days} days ago',
                 '-n', '1000',
                 '--no-pager',
                 '--output=short-iso'],        # ISO timestamps → easier to parse
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                return logs

            current_year = datetime.now().year

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue

                timestamp = ''
                log_date  = ''

                # --output=short-iso gives lines like:
                # 2024-01-15T10:23:45+0000 hostname service[pid]: message
                try:
                    ts_part   = line.split(' ')[0]           # '2024-01-15T10:23:45+0000'
                    ts_clean  = ts_part[:19]                 # '2024-01-15T10:23:45'
                    dt        = datetime.fromisoformat(ts_clean)
                    timestamp = dt.isoformat()[:19]
                    log_date  = dt.strftime('%Y-%m-%d')
                except Exception:
                    # Fallback: try classic syslog format
                    # Jan 15 10:23:45 hostname service: message
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            ts_str    = f"{parts[0]} {parts[1]} {parts[2]}"
                            dt        = datetime.strptime(
                                f"{current_year} {ts_str}", "%Y %b %d %H:%M:%S"
                            )
                            timestamp = dt.isoformat()[:19]
                            log_date  = dt.strftime('%Y-%m-%d')
                        except Exception:
                            timestamp = datetime.now().isoformat()[:19]
                            log_date  = datetime.now().strftime('%Y-%m-%d')
                    else:
                        timestamp = datetime.now().isoformat()[:19]
                        log_date  = datetime.now().strftime('%Y-%m-%d')

                logs.append({
                    'log_type':  'journal',
                    'message':   line[:250],
                    'timestamp': timestamp,
                    'source':    'journalctl',
                    'log_date':  log_date,
                })

        except subprocess.TimeoutExpired:
            print("journalctl timed out")
        except FileNotFoundError:
            print("journalctl not found")
        except Exception as e:
            print(f"Error reading logs: {e}")

        return logs

    def _recent(self):
        """
        Find recently accessed files via recently-used.xbel and common folders.
        """
        recent = []
        home   = os.path.expanduser('~')

        # Parse recently-used.xbel
        xbel = os.path.join(home, '.local', 'share', 'recently-used.xbel')
        if os.path.exists(xbel):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(xbel)
                root = tree.getroot()
                ns   = {'b': 'http://www.freedesktop.org/standards/desktop-bookmarks'}
                for bookmark in root.findall('.//b:bookmark', ns)[:100]:
                    href     = bookmark.get('href', '')
                    modified = bookmark.get('modified', '')
                    if href:
                        recent.append({
                            'name':          os.path.basename(href)[:200],
                            'target_path':   href[:500],
                            'accessed_time': modified[:19] if modified else datetime.now().isoformat()[:19],
                            'file_type':     'Recent File',
                            'access_date':   modified[:10] if modified else datetime.now().strftime('%Y-%m-%d'),
                        })
            except Exception as e:
                print(f"Error parsing recently-used.xbel: {e}")

        # Scan common user folders
        for folder in [
            os.path.join(home, 'Downloads'),
            os.path.join(home, 'Documents'),
            '/tmp',
        ]:
            if not os.path.exists(folder):
                continue
            try:
                for fname in os.listdir(folder)[:50]:
                    fp = os.path.join(folder, fname)
                    try:
                        mtime = os.path.getmtime(fp)
                        dt    = datetime.fromtimestamp(mtime)
                        if self.is_recent(dt):
                            recent.append({
                                'name':          fname[:200],
                                'target_path':   fp[:500],
                                'accessed_time': dt.isoformat()[:19],
                                'file_type':     'Folder' if os.path.isdir(fp) else 'File',
                                'access_date':   dt.strftime('%Y-%m-%d'),
                            })
                    except OSError:
                        continue
            except Exception as e:
                print(f"Error scanning {folder}: {e}")

        return recent