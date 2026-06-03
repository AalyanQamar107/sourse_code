"""
Main forensic orchestrator: coordinates collectors and database storage.
"""
import platform
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from database import clear_all, insert_many, get_all_data

class ForensicAnalyzer:
    """
    High-level controller that runs all collectors for the current OS.
    """

    def __init__(self):
        self.os_type = self._detect_os()
        self.is_admin = self._check_admin()
        print(f"[ForensicAnalyzer] Initialized for OS: {self.os_type}")

    def _detect_os(self):
        """
        Detect actual OS type, handling special cases like Wine.
        """
        system = platform.system().lower()
        
        # Check sys.platform first (more reliable on Linux)
        if sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('darwin'):
            return 'macos'
        
        # Fallback to platform.system()
        if 'linux' in system:
            return 'linux'
        elif 'windows' in system:
            return 'windows'
        elif 'darwin' in system:
            return 'macos'
        
        return system

    def _check_admin(self):
        """Check if running with elevated privileges."""
        if self.os_type == 'windows':
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        else:
            try:
                return os.geteuid() == 0
            except:
                return False

    def get_info(self):
        """Return basic system information."""
        return {
            'os': self.os_type,
            'hostname': platform.node(),
            'is_admin': self.is_admin,
            'platform': platform.system(),
            'sys_platform': sys.platform
        }

    def collect_all(self):
        """
        Clear existing data and run all collectors.
        Returns a dict with counts per category.
        """
        clear_all()
        counts = {}

        if self.os_type == 'windows':
            counts = self._collect_windows()
        elif self.os_type == 'linux':
            counts = self._collect_linux()
        else:
            print(f"Unsupported OS: {self.os_type}")
            counts = {'error': f'Unsupported OS: {self.os_type}'}

        return {'success': True, 'collected': counts, 'system_info': self.get_info()}

    def _collect_windows(self):
        """Run all Windows collectors concurrently."""
        from collectors.windows import BrowserCollector, EventCollector, PrefetchCollector, RecentCollector, USBCollector

        collectors = [
            ('browser_history', BrowserCollector),
            ('event_logs', EventCollector),
            ('prefetch_files', PrefetchCollector),
            ('recent_files', RecentCollector),
            ('usb_devices', USBCollector),
        ]

        counts = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(collector().collect): name for name, collector in collectors}
            for future in futures:
                name = futures[future]
                try:
                    data = future.result()
                    if data:
                        insert_many(name, data)
                    counts[name] = len(data) if data else 0
                    print(f"✓ {name}: {counts[name]}")
                except Exception as e:
                    print(f"✗ {name}: {e}")
                    counts[name] = 0
        return counts

    def _collect_linux(self):
        """Run all Linux collectors."""
        from collectors.linux import LinuxBrowserCollector, LinuxSystemCollector, LinuxUSBCollector

        counts = {}

        # Browser history
        try:
            print("Starting Linux browser history collection...")
            browser_collector = LinuxBrowserCollector()
            data = browser_collector.collect()
            if data:
                insert_many('browser_history', data)
            counts['browser_history'] = len(data) if data else 0
            print(f"✓ browser_history: {counts['browser_history']}")
        except Exception as e:
            print(f"✗ browser_history: {e}")
            counts['browser_history'] = 0

        # USB devices (dedicated collector)
        try:
            print("Starting Linux USB device collection...")
            usb_collector = LinuxUSBCollector()
            usb_data = usb_collector.collect()
            if usb_data:
                insert_many('usb_devices', usb_data)
            counts['usb_devices'] = len(usb_data) if usb_data else 0
            print(f"✓ usb_devices: {counts['usb_devices']}")
        except Exception as e:
            print(f"✗ usb_devices: {e}")
            counts['usb_devices'] = 0

        # System logs and recent files
        try:
            print("Starting Linux system collection...")
            system_collector = LinuxSystemCollector()
            data = system_collector.collect()
            
            # Insert system logs
            system_logs = data.get('system_logs', [])
            if system_logs:
                insert_many('system_logs', system_logs)
            counts['system_logs'] = len(system_logs)
            print(f"✓ system_logs: {counts['system_logs']}")
            
            # Insert recent files
            recent_files = data.get('recent_files', [])
            if recent_files:
                insert_many('recent_files', recent_files)
            counts['recent_files'] = len(recent_files)
            print(f"✓ recent_files: {counts['recent_files']}")
            
        except Exception as e:
            print(f"✗ Linux system collection: {e}")
            counts['system_logs'] = 0
            counts['recent_files'] = 0

        return counts

    def get_data(self):
        """Return all stored data from the database."""
        return get_all_data()