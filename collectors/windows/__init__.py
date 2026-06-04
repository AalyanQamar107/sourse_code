# collectors/windows/__init__.py
"""
Windows-specific collectors for forensic analysis.
"""

from .browser import BrowserCollector
from .events import EventCollector  # Changed from 'event' to 'events'
from .prefetch import PrefetchCollector
from .recent import RecentCollector
from .usb import USBCollector

__all__ = [
    'BrowserCollector',
    'EventCollector',
    'PrefetchCollector',
    'RecentCollector',
    'USBCollector'
]