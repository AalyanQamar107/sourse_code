"""
Browser history collector for Windows (Chrome, Edge, Opera, Brave, Firefox).
"""
import os
import sqlite3
import shutil
import tempfile
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from ..base_collector import BaseCollector

class BrowserCollector(BaseCollector):
    """
    Collects recent browsing history from multiple browsers.
    """

    def __init__(self):
        """Initialize the collector."""
        super().__init__()
        self.local = os.path.join(os.environ.get('LOCALAPPDATA', ''))
        self.roaming = os.path.join(os.environ.get('APPDATA', ''))

    def collect(self):
        """
        Locate browser profiles and collect history concurrently.
        """
        browsers = []

        # Chrome
        chrome_path = os.path.join(self.local, 'Google', 'Chrome', 'User Data')
        if os.path.exists(chrome_path):
            browsers.append(('Chrome', chrome_path))

        # Edge
        edge_path = os.path.join(self.local, 'Microsoft', 'Edge', 'User Data')
        if os.path.exists(edge_path):
            browsers.append(('Edge', edge_path))

        # Brave
        brave_path = os.path.join(self.local, 'BraveSoftware', 'Brave-Browser', 'User Data')
        if os.path.exists(brave_path):
            browsers.append(('Brave', brave_path))

        # Opera
        opera_path = os.path.join(self.roaming, 'Opera Software', 'Opera Stable')
        if os.path.exists(opera_path):
            browsers.append(('Opera', opera_path))

        # Firefox
        firefox_path = os.path.join(self.roaming, 'Mozilla', 'Firefox', 'Profiles')
        if os.path.exists(firefox_path):
            browsers.append(('Firefox', firefox_path))

        history = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self._collect_browser, name, path)
                for name, path in browsers
            ]
            for future in futures:
                try:
                    history.extend(future.result())
                except Exception as e:
                    print(f"Browser collection error: {e}")
        return history

    def _collect_browser(self, name, path):
        """
        Dispatch to the appropriate method based on browser name.
        """
        if name == 'Firefox':
            return self._firefox(path)
        return self._chromium(name, path)

    def _chromium(self, browser, base):
        """
        Extract history from Chromium-based browsers.
        """
        history = []
        epoch = datetime(1601, 1, 1)
        cutoff_ts = int((self.cutoff - epoch).total_seconds() * 1_000_000)

        try:
            # Find all profiles
            profiles = []
            for item in os.listdir(base):
                hp = os.path.join(base, item, 'History')
                if os.path.exists(hp):
                    profiles.append((item, hp))
            
            # Check Default profile
            default_hp = os.path.join(base, 'Default', 'History')
            if os.path.exists(default_hp) and ('Default', default_hp) not in profiles:
                profiles.append(('Default', default_hp))

            for profile, hp in profiles[:10]:
                temp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
                temp.close()
                try:
                    shutil.copy2(hp, temp.name)
                    conn = sqlite3.connect(temp.name, timeout=10)
                    conn.text_factory = bytes
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        '''SELECT url, title, visit_count, last_visit_time 
                           FROM urls 
                           WHERE last_visit_time > ? 
                           ORDER BY last_visit_time DESC 
                           LIMIT 2000''',
                        (cutoff_ts,)
                    )
                    
                    for row in cursor.fetchall():
                        url = row[0].decode('utf-8', errors='ignore') if row[0] else ''
                        title = row[1].decode('utf-8', errors='ignore') if row[1] else ''
                        cnt = row[2] or 0
                        vt = row[3]
                        
                        if vt:
                            dt = epoch + timedelta(microseconds=vt)
                            if self.is_recent(dt):
                                history.append({
                                    'browser': browser,
                                    'profile': profile,
                                    'url': url[:500],
                                    'title': title[:200],
                                    'visit_time': dt.isoformat()[:19],
                                    'visit_count': cnt,
                                    'visit_date': dt.strftime('%Y-%m-%d')
                                })
                    conn.close()
                except Exception as e:
                    print(f"Error reading {browser}/{profile}: {e}")
                finally:
                    try:
                        os.unlink(temp.name)
                    except:
                        pass
        except Exception as e:
            print(f"Error accessing {browser} profiles: {e}")
        
        return history

    def _firefox(self, base):
        """
        Extract history from Firefox profiles.
        """
        history = []
        cutoff_ts = int(self.cutoff.timestamp() * 1_000_000)

        try:
            for profile in os.listdir(base)[:5]:
                places = os.path.join(base, profile, 'places.sqlite')
                if not os.path.exists(places):
                    continue

                temp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
                temp.close()
                try:
                    shutil.copy2(places, temp.name)
                    conn = sqlite3.connect(temp.name, timeout=10)
                    conn.text_factory = bytes
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        '''SELECT DISTINCT p.url, p.title, p.visit_count, h.visit_date
                           FROM moz_places p
                           JOIN moz_historyvisits h ON p.id = h.place_id
                           WHERE h.visit_date > ?
                           ORDER BY h.visit_date DESC
                           LIMIT 2000''',
                        (cutoff_ts,)
                    )
                    
                    for row in cursor.fetchall():
                        url = row[0].decode('utf-8', errors='ignore') if row[0] else ''
                        title = row[1].decode('utf-8', errors='ignore') if row[1] else ''
                        cnt = row[2] or 0
                        vt = row[3]
                        
                        if vt:
                            dt = datetime.fromtimestamp(vt / 1_000_000)
                            if self.is_recent(dt):
                                history.append({
                                    'browser': 'Firefox',
                                    'profile': profile,
                                    'url': url[:500],
                                    'title': title[:200],
                                    'visit_time': dt.isoformat()[:19],
                                    'visit_count': cnt,
                                    'visit_date': dt.strftime('%Y-%m-%d')
                                })
                    conn.close()
                except Exception as e:
                    print(f"Firefox error in {profile}: {e}")
                finally:
                    try:
                        os.unlink(temp.name)
                    except:
                        pass
        except Exception as e:
            print(f"Error reading Firefox profiles: {e}")
        
        return history