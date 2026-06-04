"""
Final Fixed Linux Browser History Collector for Kali Linux
Supports standard profiles including .default-esr
"""
import os
import sqlite3
import shutil
import tempfile
from datetime import datetime, timedelta
from ..base_collector import BaseCollector

class LinuxBrowserCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.home = os.path.expanduser('~')

    def collect(self):
        history = []
        history.extend(self._collect_chromium_based())
        history.extend(self._collect_firefox())
        
        print(f"✅ Browser collection finished → {len(history)} entries found")
        return history

    # ====================== Chromium (Chrome + Chromium) ======================
    def _collect_chromium_based(self):
        history = []
        for name in ["Chrome", "Chromium"]:
            bases = [
                os.path.join(self.home, ".config", name.lower()),
                os.path.join(self.home, ".config", name.lower() + "-beta"),
                os.path.join(self.home, "snap", name.lower(), "common", "chromium"),
                os.path.join(self.home, ".var", "app", f"com.google.{name}", "config", name.lower()),
            ]
            for base in bases:
                if os.path.exists(base):
                    history.extend(self._read_chromium_profiles(base, name))
        return history

    def _read_chromium_profiles(self, base, browser):
        history = []
        epoch = datetime(1601, 1, 1)
        cutoff_ts = int((self.cutoff - epoch).total_seconds() * 1_000_000)

        for root, _, files in os.walk(base):
            if "History" in files:
                db_path = os.path.join(root, "History")
                profile = os.path.basename(root)
                history.extend(self._read_chromium_db(db_path, browser, profile, cutoff_ts))
        return history

    def _read_chromium_db(self, db_path, browser, profile, cutoff_ts):
        if not os.path.exists(db_path):
            return []
        history = []
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            shutil.copy2(db_path, tmp.name)
            conn = sqlite3.connect(tmp.name, timeout=10)
            conn.text_factory = bytes
            cur = conn.cursor()

            cur.execute("""
                SELECT url, title, visit_count, last_visit_time 
                FROM urls 
                WHERE last_visit_time > ? 
                ORDER BY last_visit_time DESC LIMIT 1500
            """, (cutoff_ts,))

            for row in cur.fetchall():
                url = row[0].decode('utf-8', errors='ignore') if row[0] else ''
                title = row[1].decode('utf-8', errors='ignore') if row[1] else ''
                if url:
                    dt = epoch + timedelta(microseconds=row[3])
                    if self.is_recent(dt):
                        history.append({
                            'browser': browser,
                            'profile': profile,
                            'url': url[:500],
                            'title': title[:200],
                            'visit_time': dt.isoformat()[:19],
                            'visit_count': row[2] or 0,
                            'visit_date': dt.strftime('%Y-%m-%d')
                        })
            conn.close()
        except Exception as e:
            print(f"Chromium error ({browser}/{profile}): {e}")
        finally:
            try: os.unlink(tmp.name)
            except: pass
        return history

    # ====================== Firefox ======================
    def _collect_firefox(self):
        history = []
        cutoff_ts = int(self.cutoff.timestamp() * 1_000_000)

        bases = [
            os.path.join(self.home, ".mozilla", "firefox"),
            os.path.join(self.home, "snap", "firefox", "common", ".mozilla", "firefox")
        ]

        for base in bases:
            if not os.path.exists(base):
                continue
            for item in os.listdir(base):
                if item == "Profile Groups":          # Skip useless folder
                    continue
                profile_dir = os.path.join(base, item)
                if os.path.isdir(profile_dir):
                    places = os.path.join(profile_dir, "places.sqlite")
                    if os.path.exists(places):
                        history.extend(self._read_firefox_db(places, item, cutoff_ts))

        return history

    def _read_firefox_db(self, db_path, profile_name, cutoff_ts):
        history = []
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            shutil.copy2(db_path, tmp.name)
            conn = sqlite3.connect(tmp.name, timeout=10)
            conn.text_factory = bytes
            cur = conn.cursor()

            cur.execute("""
                SELECT DISTINCT p.url, p.title, p.visit_count, h.visit_date
                FROM moz_places p
                JOIN moz_historyvisits h ON p.id = h.place_id
                WHERE h.visit_date > ?
                ORDER BY h.visit_date DESC LIMIT 1500
            """, (cutoff_ts,))

            for row in cur.fetchall():
                url = row[0].decode('utf-8', errors='ignore') if row[0] else ''
                title = row[1].decode('utf-8', errors='ignore') if row[1] else ''
                if url:
                    dt = datetime.fromtimestamp(row[3] / 1_000_000)
                    if self.is_recent(dt):
                        history.append({
                            'browser': 'Firefox',
                            'profile': profile_name,
                            'url': url[:500],
                            'title': title[:200],
                            'visit_time': dt.isoformat()[:19],
                            'visit_count': row[2] or 0,
                            'visit_date': dt.strftime('%Y-%m-%d')
                        })
            conn.close()
        except Exception as e:
            print(f"Firefox error in profile {profile_name}: {e}")
        finally:
            try: os.unlink(tmp.name)
            except: pass
        return history
