"""Writable data directory for logs, TLE cache, and the satellite database.

When running from source, files stay inside the project tree (existing behaviour).
When running as a PyInstaller bundle (sys.frozen), __file__ is inside the read-only
.app bundle, so we redirect to the platform user-data directory instead.
"""
import os
import sys


def app_data_dir() -> str:
    """Return (and create) the writable directory for all runtime data files."""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'darwin':
            base = os.path.expanduser('~/Library/Application Support/GPS Monitor')
        elif sys.platform == 'win32':
            base = os.path.join(
                os.environ.get('APPDATA', os.path.expanduser('~')),
                'GPS Monitor'
            )
        else:
            base = os.path.expanduser('~/.local/share/GPS Monitor')
    else:
        # Source checkout — keep files in the project root
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(base, exist_ok=True)
    return base
