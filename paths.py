# paths.py
import os
import sys
from pathlib import Path


def get_base_dir():
    """Return the directory where the executable or script lives."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


def get_reports_dir():
    """
    Returns a persistent, writable directory for reports.
    Priority:
      1. <exe_dir>/reports   (works for both frozen and dev mode)
      2. ~/Documents/ForensicReports  (fallback if the above is not writable)
    """
    # Prefer a 'reports' folder next to the script / executable
    primary = Path(get_base_dir()) / "reports"
    try:
        primary.mkdir(parents=True, exist_ok=True)
        # Quick write-permission test
        test_file = primary / ".write_test"
        test_file.touch()
        test_file.unlink()
        return str(primary)
    except OSError:
        pass

    # Fallback: user Documents folder
    fallback = Path.home() / "Documents" / "ForensicReports"
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback)