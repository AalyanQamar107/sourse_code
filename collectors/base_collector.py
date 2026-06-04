"""
Base class for all collectors. Provides common date handling utilities.
"""
import platform
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

class BaseCollector(ABC):
    """
    Abstract base collector that defines the interface and common methods.
    """
    os_type = platform.system().lower()
    days = 30  # Number of days to look back
    cutoff = datetime.now() - timedelta(days=days)

    def is_recent(self, dt):
        """
        Check if a given datetime is within the cutoff period.
        Supports both datetime objects and ISO format strings.
        """
        if isinstance(dt, str):
            try:
                # Parse ISO format, truncate to seconds if needed
                dt = datetime.fromisoformat(dt.replace('Z', '').split('.')[0][:19])
            except Exception:
                # If parsing fails, assume it's recent
                return True
        return dt >= self.cutoff

    def get_date(self, dt):
        """
        Extract date string (YYYY-MM-DD) from a datetime object or ISO string.
        """
        if isinstance(dt, str):
            try:
                return dt[:10]  # Simple truncation
            except Exception:
                pass
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d')
        return datetime.now().strftime('%Y-%m-%d')

    @abstractmethod
    def collect(self):
        """
        Main collection method to be implemented by subclasses.
        Returns a list of dictionaries (artifacts).
        """
        return []