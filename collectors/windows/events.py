import subprocess
import json
from ..base_collector import BaseCollector

class EventCollector(BaseCollector):

    def collect(self):
        events = []
        for log in ['System', 'Application', 'Security']:
            events.extend(self._get_log(log))
        return events[:5000]

    def _get_log(self, log_type):
        events = []
        try:
            ps = f'''
            Get-WinEvent -FilterHashtable @{{LogName='{log_type}';StartTime=(Get-Date).AddDays(-{self.days})}} -MaxEvents 2000 -EA 0 |
            Select Id,ProviderName,@{{N='Msg';E={{$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}}}},
            @{{N='Time';E={{$_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss')}}}},LevelDisplayName,
            @{{N='Date';E={{$_.TimeCreated.ToString('yyyy-MM-dd')}}}} | ConvertTo-Json -Compress
            '''
            r = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW   # <-- hide PowerShell window
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    events.append({
                        'log_type': log_type,
                        'event_id': d.get('Id', 0),
                        'source': str(d.get('ProviderName', ''))[:100],
                        'message': str(d.get('Msg', ''))[:250],
                        'time_generated': d.get('Time', ''),
                        'level': d.get('LevelDisplayName', ''),
                        'event_date': d.get('Date', '')
                    })
        except Exception as e:
            print(f"Event log error {log_type}: {e}")
        return events