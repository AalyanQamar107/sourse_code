"""
Recent files collector for Windows (Recent folder, Shell Recent, common folders).
"""
import os
import subprocess
import json
from datetime import datetime
from ..base_collector import BaseCollector

class RecentCollector(BaseCollector):

    def collect(self):
        recent = []
        user = os.path.expanduser('~')
        paths = [
            os.path.join(user, 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Recent'),
            os.path.join(user, 'Recent'),
        ]
        for path in paths:
            if os.path.exists(path):
                recent.extend(self._collect_from_path(path))
        recent.extend(self._collect_from_shell())
        recent.extend(self._collect_common_folders())
        return recent

    def _collect_from_path(self, path):
        files = []
        try:
            for filename in os.listdir(path):
                filepath = os.path.join(path, filename)
                try:
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        atime = datetime.fromtimestamp(stat.st_atime)
                        use_time = max(mtime, atime)
                        if self.is_recent(use_time):
                            ext = os.path.splitext(filename)[1].lower()
                            target = self._get_target(filepath) if ext == '.lnk' else filepath
                            files.append({
                                'name': filename[:200],
                                'target_path': target[:500],
                                'accessed_time': use_time.isoformat()[:19],
                                'file_type': self._get_type(filename),
                                'access_date': use_time.strftime('%Y-%m-%d')
                            })
                except OSError:
                    continue
        except Exception as e:
            print(f"Error scanning {path}: {e}")
        return files

    def _collect_from_shell(self):
        files = []
        try:
            ps_command = '''
            $shell = New-Object -ComObject Shell.Application
            $recent = $shell.Namespace('shell:Recent')
            $items = $recent.Items()
            $result = @()
            foreach ($item in $items) {
                $result += [PSCustomObject]@{
                    Name = $item.Name
                    Path = $item.Path
                    Date = $item.ModifyDate
                }
            }
            $result | ConvertTo-Json -Compress
            '''
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_command],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW   # <-- hide PowerShell
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                for entry in data[:200]:
                    name = entry.get('Name', '')
                    if name:
                        files.append({
                            'name': str(name)[:200],
                            'target_path': str(entry.get('Path', ''))[:500],
                            'accessed_time': datetime.now().isoformat()[:19],
                            'file_type': self._get_type(name),
                            'access_date': datetime.now().strftime('%Y-%m-%d')
                        })
        except Exception as e:
            print(f"Shell recent error: {e}")
        return files

    def _collect_common_folders(self):
        files = []
        user = os.path.expanduser('~')
        folders = [
            os.path.join(user, 'Desktop'),
            os.path.join(user, 'Downloads'),
            os.path.join(user, 'Documents'),
        ]
        for folder in folders:
            if os.path.exists(folder):
                try:
                    for filename in os.listdir(folder)[:50]:
                        filepath = os.path.join(folder, filename)
                        try:
                            mtime = os.path.getmtime(filepath)
                            dt = datetime.fromtimestamp(mtime)
                            if self.is_recent(dt):
                                files.append({
                                    'name': filename[:200],
                                    'target_path': filepath[:500],
                                    'accessed_time': dt.isoformat()[:19],
                                    'file_type': 'Folder' if os.path.isdir(filepath) else self._get_type(filename),
                                    'access_date': dt.strftime('%Y-%m-%d')
                                })
                        except OSError:
                            continue
                except Exception as e:
                    print(f"Error scanning {folder}: {e}")
        return files

    def _get_target(self, lnk_path):
        try:
            ps_command = f'''
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut("{lnk_path}")
            $shortcut.TargetPath
            '''
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_command],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW   # <-- hide PowerShell
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return lnk_path

    def _get_type(self, name):
        ext = os.path.splitext(name)[1].lower()
        types = {
            '.lnk': 'Shortcut', '.doc': 'Document', '.docx': 'Document',
            '.pdf': 'PDF', '.xlsx': 'Spreadsheet', '.xls': 'Spreadsheet',
            '.txt': 'Text', '.jpg': 'Image', '.png': 'Image', '.jpeg': 'Image',
            '.exe': 'Executable', '.zip': 'Archive', '.rar': 'Archive',
            '.mp3': 'Audio', '.mp4': 'Video', '.pptx': 'Presentation',
        }
        return types.get(ext, 'File')