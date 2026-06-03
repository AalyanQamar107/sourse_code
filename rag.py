"""
Hybrid RAG (Retrieval-Augmented Generation) module.
Fixed: system logs keyword mapping, Linux artifact type detection.
"""
import os, sys
import re
from datetime import datetime, timedelta
from database import query

class HybridRAG:

    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
            
        self.model_path = os.path.join(
            base_dir, "models", "llama-3.2-3b-instruct-q4_k_m.gguf"
        )
        self.llm  = None
        self.days = 30
        print(f"[RAG] Looking for model at: {self.model_path}")
        self.load_llm()

    

    def load_llm(self):
        if self.llm:
            return True
        if not os.path.exists(self.model_path):
            print("⚠️  LLM model not found. Summaries will be basic.")
            return False

        try:
            from llama_cpp import Llama
            print(f"✅ llama_cpp imported. Loading model from {self.model_path}...")
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False
            )
            print("✅ Model loaded successfully.")
            return True
        except ImportError as e:
            print(f"❌ llama_cpp not installed or not bundled: {e}")
            return False
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return False
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False
            )
            return True
        except ImportError:
            print("llama-cpp-python not installed. LLM disabled.")
            return False
        except Exception as e:
            print(f"LLM load error: {e}")
            return False

    def parse_date(self, query_text):
        q     = query_text.lower()
        today = datetime.now()

        if 'today' in q:
            return today.strftime('%Y-%m-%d')
        if 'yesterday' in q:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')

        m = re.search(r'(\d+)\s*days?\s*ago', q)
        if m and int(m.group(1)) <= self.days:
            return (today - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%d')

        months = {
            'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
            'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
            'january':1,'february':2,'march':3,'april':4,'june':6,
            'july':7,'august':8,'september':9,'october':10,
            'november':11,'december':12
        }
        for name, num in months.items():
            for pattern in [rf'(\d{{1,2}})\s*{name}', rf'{name}\s*(\d{{1,2}})']:
                m = re.search(pattern, q)
                if m:
                    try:
                        day = int(m.group(1))
                        dt  = datetime(today.year, num, day)
                        if dt > today:
                            dt = datetime(today.year - 1, num, day)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
        return None

    def parse_types(self, query_text):
        """
        Fixed: 'system logs', 'journal', 'kernel' now correctly map
        to system_logs table (Linux). 'event logs' maps to event_logs (Windows).
        """
        q = query_text.lower()

        # Prefetch (Windows only)
        if any(w in q for w in [
            'prefetch', '.pf', 'pf file', 'executed', 'program run'
        ]):
            return ['prefetch_files']

        # Recent files
        if any(w in q for w in [
            'recent file', 'recent folder', 'recently opened',
            'recently accessed', 'recent files'
        ]):
            return ['recent_files']

        # USB
        if any(w in q for w in [
            'usb', 'device connected', 'pendrive',
            'flash drive', 'external drive', 'external storage'
        ]):
            return ['usb_devices', 'usb_connections', 'usb_history']

        # ✅ Fix: system logs (Linux journalctl) — check BEFORE generic 'log'
        if any(w in q for w in [
            'system log', 'system logs', 'journal', 'journalctl',
            'kernel', 'syslog', 'kernel log', 'linux log'
        ]):
            return ['system_logs']

        # Event logs (Windows)
        if any(w in q for w in [
            'event log', 'event logs', 'windows log',
            'security log', 'application log'
        ]):
            return ['event_logs']

        # Generic 'log' — return both so it works on both OS
        if 'log' in q:
            return ['event_logs', 'system_logs']

        # Browser
        if any(w in q for w in [
            'browser', 'chrome', 'edge', 'firefox', 'opera',
            'brave', 'url', 'website', 'history', 'browsing'
        ]):
            return ['browser_history']

        return None

    def parse_browser(self, query_text):
        q = query_text.lower()
        for browser in ['chrome', 'edge', 'firefox', 'opera', 'brave']:
            if browser in q:
                return browser.capitalize()
        return None

    def parse_usb_type(self, query_text):
        q = query_text.lower()
        if 'external' in q and 'internal' not in q:
            return 'external'
        if 'internal' in q and 'external' not in q:
            return 'internal'
        return None

    def validate(self, query_text):
        q = query_text.lower()
        if re.search(r'(\d+)\s*months?\s*ago', q):
            return False, f"❌ Data only available for the last {self.days} days."
        m = re.search(r'(\d+)\s*days?\s*ago', q)
        if m and int(m.group(1)) > self.days:
            return False, f"❌ Data only available for the last {self.days} days."
        return True, ""

    def get_data(self, query_text):
        types    = self.parse_types(query_text)
        date     = self.parse_date(query_text)
        browser  = self.parse_browser(query_text)
        usb_type = self.parse_usb_type(query_text)

        tables = types if types else [
            'browser_history', 'event_logs', 'prefetch_files',
            'recent_files', 'usb_devices', 'usb_connections',
            'usb_history', 'system_logs'
        ]

        date_col_map = {
            'browser_history': 'visit_date',
            'event_logs':      'event_date',
            'prefetch_files':  'run_date',
            'recent_files':    'access_date',
            'usb_devices':     'connect_date',
            'usb_connections': 'event_date',
            'usb_history':     'connect_date',
            'system_logs':     'log_date',
        }

        results = {}
        for table in tables:
            sql    = f'SELECT * FROM {table} WHERE 1=1'
            params = []

            date_col = date_col_map.get(table)
            if date and date_col:
                sql += f' AND {date_col}=?'
                params.append(date)

            if table == 'browser_history' and browser:
                sql += ' AND LOWER(browser)=?'
                params.append(browser.lower())

            if table == 'usb_devices' and usb_type:
                if usb_type == 'external':
                    sql += " AND connection_type LIKE '%External%'"
                else:
                    sql += " AND connection_type LIKE '%Internal%'"

            sql += ' LIMIT 200'
            results[table] = query(sql, params)

        return results

    def generate(self, q, data):
        total = sum(len(v) for v in data.values())
        if total == 0:
            date = self.parse_date(q)
            if date:
                return f"No data found for {date}. Data available for last {self.days} days."
            return "No matching data found for your query."

        llm_loaded = self.load_llm()
        if llm_loaded and total > 0:
            try:
                context_lines = []
                for table, items in data.items():
                    if items:
                        context_lines.append(
                            f"--- {table} ({len(items)} items) ---"
                        )
                        for item in items[:10]:
                            fields = []
                            if table == 'browser_history':
                                fields = [
                                    f"Browser: {item.get('browser')}",
                                    f"Title: {str(item.get('title',''))[:50]}",
                                    f"URL: {str(item.get('url',''))[:50]}",
                                    f"Time: {item.get('visit_time')}"
                                ]
                            elif table == 'event_logs':
                                fields = [
                                    f"Log: {item.get('log_type')}",
                                    f"ID: {item.get('event_id')}",
                                    f"Source: {item.get('source')}",
                                    f"Msg: {str(item.get('message',''))[:50]}"
                                ]
                            elif table == 'system_logs':
                                fields = [
                                    f"Type: {item.get('log_type')}",
                                    f"Source: {item.get('source')}",
                                    f"Msg: {str(item.get('message',''))[:50]}",
                                    f"Time: {item.get('timestamp')}"
                                ]
                            elif table == 'prefetch_files':
                                fields = [
                                    f"EXE: {item.get('exe_name')}",
                                    f"Run count: {item.get('run_count')}",
                                    f"Last: {item.get('last_run')}"
                                ]
                            elif table == 'recent_files':
                                fields = [
                                    f"File: {item.get('name')}",
                                    f"Path: {str(item.get('target_path',''))[:50]}",
                                    f"Accessed: {item.get('accessed_time')}"
                                ]
                            elif table in ('usb_devices', 'usb_history'):
                                fields = [
                                    f"Device: {item.get('device_name')}",
                                    f"Type: {item.get('connection_type')}",
                                    f"Last seen: {item.get('last_connected')}"
                                ]
                            elif table == 'usb_connections':
                                fields = [
                                    f"Device: {item.get('device_name')}",
                                    f"Event: {item.get('event_type')}",
                                    f"Time: {item.get('event_time')}"
                                ]
                            else:
                                fields = [
                                    f"{k}: {v}"
                                    for k, v in list(item.items())[:3]
                                ]
                            context_lines.append(
                                " - " + " | ".join(str(f) for f in fields)
                            )

                context = "\n".join(context_lines)[:2000]
                prompt  = (
                    "You are a digital forensics assistant. Answer the user's "
                    "question based on the provided forensic data.\n"
                    "Be concise and highlight key findings, dates, and patterns.\n\n"
                    f"Forensic data:\n{context}\n\n"
                    f"User question: {q}\n\nYour answer:"
                )
                response = self.llm(
                    prompt, max_tokens=300, temperature=0.2,
                    stop=["User question:"]
                )
                if response and response.get('choices'):
                    llm_answer = response['choices'][0]['text'].strip()
                    return llm_answer + f"\n\n**Total artifacts found:** {total}"
            except Exception as e:
                print(f"LLM generation failed: {e}")

        # Fallback plain summary
        lines = [f"## Forensic Analysis Results\n", f"**Query:** {q}\n"]
        for table, items in data.items():
            if items:
                name = table.replace('_', ' ').title()
                lines.append(f"\n### {name} ({len(items)} items)\n")
                for item in items[:5]:
                    parts = [
                        f"**{k}**: {str(v)[:40]}"
                        for k, v in list(item.items())[:4]
                        if k != 'id'
                    ]
                    lines.append(f"- {' | '.join(parts)}")
                if len(items) > 5:
                    lines.append(f"- ... and {len(items) - 5} more")
        lines.append(f"\n**Total:** {total} artifacts found.")
        return '\n'.join(lines)

    def query(self, user_query):
        valid, msg = self.validate(user_query)
        if not valid:
            return {'success': False, 'response': msg, 'data': []}

        data  = self.get_data(user_query)
        total = sum(len(v) for v in data.values())

        if total == 0:
            types = self.parse_types(user_query)
            date  = self.parse_date(user_query)
            msg   = "No data found."
            if date:
                msg = f"No data found for {date}."
            if types:
                msg += f" Searched: {', '.join(types).replace('_', ' ')}"
            return {'success': False, 'response': msg, 'data': []}

        response  = self.generate(user_query, data)
        flat_data = [item for items in data.values() for item in items]

        return {
            'success':        True,
            'response':       response,
            'data':           flat_data[:200],
            'query_type':     self.parse_types(user_query),
            'date_filter':    self.parse_date(user_query),
            'browser_filter': self.parse_browser(user_query),
        }