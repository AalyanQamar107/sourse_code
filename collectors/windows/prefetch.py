"""
Windows Prefetch file collector.
"""
import os
from datetime import datetime
from ..base_collector import BaseCollector

class PrefetchCollector(BaseCollector):
    """
    Collects recently run programs from C:\\Windows\\Prefetch.
    """

    def collect(self):
        """
        Scan Prefetch folder and extract metadata from .pf files.
        """
        prefetch = []
        path = r'C:\Windows\Prefetch'
        if not os.path.exists(path):
            return prefetch

        try:
            for filename in os.listdir(path):
                if filename.upper().endswith('.PF'):
                    filepath = os.path.join(path, filename)
                    try:
                        mtime = os.path.getmtime(filepath)
                        dt = datetime.fromtimestamp(mtime)
                        if self.is_recent(dt):
                            # Basic parsing: extract executable name (before first hyphen)
                            exe_name = filename.split('-')[0] if '-' in filename else filename[:-3]
                            prefetch.append({
                                'filename': filename,
                                'exe_name': exe_name,
                                'run_count': 1,  # Prefetch doesn't store count directly
                                'last_run': dt.isoformat()[:19],
                                'file_path': filepath,
                                'run_date': dt.strftime('%Y-%m-%d')
                            })
                    except OSError as e:
                        print(f"Error accessing {filename}: {e}")
        except Exception as e:
            print(f"Prefetch scan error: {e}")
        return prefetch