# utils/log_config.py

Central logging configuration. Call `setup()` once at startup in `main.py`.

## `setup(level=logging.DEBUG)`

Configures the Python root logger. Idempotent — returns immediately if handlers are already attached.

### Handlers

| Handler | Level | Destination | Format |
|---------|-------|-------------|--------|
| `RotatingFileHandler` | DEBUG | `logs/gps_monitor.log` | `%(asctime)s  %(levelname)-8s  %(name)s: %(message)s` |
| `StreamHandler` | WARNING | stdout | same format |

### File Rotation

1 MB per file, 5 backup files kept (`gps_monitor.log.1` … `.5`). UTF-8 encoding.

### Usage in Other Modules

```python
import logging
log = logging.getLogger(__name__)
log.debug("low-level detail")
log.info("normal event")
log.warning("something unexpected but handled")
log.exception("caught an exception", exc_info=True)
```

The `logs/` directory is created by `setup()` if it doesn't exist. Runtime `.log` files are excluded from git (`.gitignore`); the directory itself is tracked via `logs/.gitkeep`.
