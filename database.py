"""
SQLite database wrapper - Optimized for VirtualBox shared folders (Kali Linux)
"""
import sqlite3
import os, sys
from datetime import datetime
from threading import Lock
import sys, os
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

DB_PATH = resource_path('database/forensic_data.db')

def get_base_dir():
   
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(".")

BASE_DIR = get_base_dir()
DB_FOLDER = os.path.join(BASE_DIR, "database")
os.makedirs(DB_FOLDER, exist_ok=True)

DB_PATH = os.path.join(DB_FOLDER, "forensic_data.db")
_lock = Lock()

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    with _lock:
        conn = get_conn()
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS browser_history (
                id INTEGER PRIMARY KEY, browser TEXT, profile TEXT, url TEXT, title TEXT,
                visit_time TEXT, visit_count INTEGER, visit_date TEXT
            );
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY, log_type TEXT, event_id INTEGER, source TEXT,
                message TEXT, time_generated TEXT, level TEXT, event_date TEXT
            );
            CREATE TABLE IF NOT EXISTS prefetch_files (
                id INTEGER PRIMARY KEY, filename TEXT, exe_name TEXT, run_count INTEGER,
                last_run TEXT, file_path TEXT, run_date TEXT
            );
            CREATE TABLE IF NOT EXISTS recent_files (
                id INTEGER PRIMARY KEY, name TEXT, target_path TEXT, accessed_time TEXT,
                file_type TEXT, access_date TEXT
            );
            CREATE TABLE IF NOT EXISTS usb_devices (
                id INTEGER PRIMARY KEY, device_name TEXT, device_id TEXT, connection_type TEXT,
                last_connected TEXT, serial_number TEXT, vendor TEXT, product_id TEXT,
                speed TEXT, mount_point TEXT, connect_date TEXT
            );
            CREATE TABLE IF NOT EXISTS usb_connections (
                id INTEGER PRIMARY KEY, device_name TEXT, event_type TEXT, event_time TEXT,
                device_id TEXT, event_date TEXT
            );
            CREATE TABLE IF NOT EXISTS usb_history (
                id INTEGER PRIMARY KEY, device_name TEXT, instance_id TEXT, last_connected TEXT,
                is_present INTEGER, connect_date TEXT, vendor TEXT, product_id TEXT,
                speed TEXT, mount_point TEXT
            );
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY, log_type TEXT, message TEXT, timestamp TEXT,
                source TEXT, log_date TEXT
            );
            CREATE TABLE IF NOT EXISTS chain_of_custody (
                id INTEGER PRIMARY KEY, timestamp TEXT, user TEXT, action TEXT,
                description TEXT, artifact_hash TEXT, details TEXT
            );
        ''')

       
        index_targets = [
            ('browser_history', 'visit_date'),
            ('event_logs',      'event_date'),
            ('prefetch_files',  'run_date'),
            ('recent_files',    'access_date'),
            ('usb_devices',     'connect_date'),
            ('usb_connections', 'event_date'),
            ('usb_history',     'connect_date'),
            ('system_logs',     'log_date'),
        ]
        for table, date_col in index_targets:
            try:
                c.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_date "
                    f"ON {table}({date_col})"
                )
            except Exception:
                pass

        conn.commit()
        conn.close()
        print(f"✅ DB ready → {DB_PATH}")

def clear_all():
    with _lock:
        conn = get_conn()
        tables = [
            'browser_history', 'event_logs', 'prefetch_files', 'recent_files',
            'usb_devices', 'usb_connections', 'usb_history', 'system_logs'
        ]
        for t in tables:
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.close()

def insert_many(table, data_list):
    if not data_list:
        return
    with _lock:
        conn = get_conn()
        keys = sorted({k for d in data_list for k in d})
        placeholders = ','.join(['?'] * len(keys))
        sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
        rows = [[d.get(k) for k in keys] for d in data_list]
        conn.executemany(sql, rows)
        conn.commit()
        conn.close()

def query(sql, params=()):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

def get_all_data():
    tables = [
        'browser_history', 'event_logs', 'prefetch_files', 'recent_files',
        'usb_devices', 'usb_connections', 'usb_history', 'system_logs'
    ]
    return {t: query(f"SELECT * FROM {t}") for t in tables}