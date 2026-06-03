"""
JSON Import/Export for forensic data.
Handles export of all tables and import from previously exported JSON.
"""
import json
import os
from datetime import datetime
from database import query, insert_many, clear_all
from paths import get_base_dir

# All tables that will be exported/imported
ALL_TABLES = [
    'browser_history', 'event_logs', 'prefetch_files', 'recent_files',
    'usb_devices', 'usb_connections', 'usb_history', 'system_logs'
]

def get_exports_dir():
    """Get a persistent directory for exports, next to the executable."""
    base = get_base_dir()
    exports_dir = os.path.join(base, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    return exports_dir

def export_to_json(filepath=None):
    """
    Export all data from all tables to a JSON file.
    Returns the filepath of the created JSON file.
    """
    if not filepath:
        exports_dir = get_exports_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(exports_dir, f"export_{timestamp}.json")
    data = {}
    for table in ALL_TABLES:
        data[table] = query(f"SELECT * FROM {table}")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    return filepath

def import_from_json(filepath, clear_existing=False):
    """
    Import data from a JSON file into the database.
    If clear_existing is True, all existing data is cleared before import.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if clear_existing:
        clear_all()

    for table, rows in data.items():
        if table in ALL_TABLES and rows:
            # Remove 'id' field from each row to avoid UNIQUE constraint errors
            cleaned_rows = []
            for row in rows:
                if 'id' in row:
                    del row['id']
                cleaned_rows.append(row)
            insert_many(table, cleaned_rows)
    return True