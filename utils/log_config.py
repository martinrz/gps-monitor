"""Central logging configuration for GPS Monitor.

Call setup() once at application startup (in main.py).
All other modules obtain their logger with logging.getLogger(__name__).
"""
import logging
import logging.handlers
import os

from utils.paths import app_data_dir

_LOG_DIR  = os.path.join(app_data_dir(), 'logs')
_LOG_FILE = os.path.join(_LOG_DIR, 'gps_monitor.log')
_FMT      = '%(asctime)s  %(levelname)-8s  %(name)s: %(message)s'
_DATE_FMT = '%Y-%m-%d %H:%M:%S'


def setup(level: int = logging.DEBUG) -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. called twice)
    root.setLevel(level)

    # Rotating file: 1 MB per file, keep 5 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding='utf-8'
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(fh)

    # Console: WARNING and above only so stdout stays quiet
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(ch)
