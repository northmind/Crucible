import logging
import sys
from datetime import datetime

from crucible.core.paths import Paths

logger = logging.getLogger(__name__)

_LOG_LEVELS = {"info": logging.INFO, "debug": logging.DEBUG, "off": logging.CRITICAL + 1}


def setup_logging() -> logging.Logger:
    """Remove old app logs and configure the root logger with file and console handlers.

    Returns:
        The module-level logger after attaching a DEBUG-level file handler
        and an INFO-level console handler to the root logger.
    """
    log_dir = Paths.app_logs_dir()

    for old_log in log_dir.glob("*.log"):
        try:
            old_log.unlink()
        except OSError as exc:
            logger.debug(f"Failed to remove old app log {old_log}: {exc}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{timestamp}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")

    return logger


def apply_log_level(level_name: str) -> None:
    """Update the console handler's log level at runtime.

    Args:
        level_name: One of ``"info"``, ``"debug"``, or ``"off"``.
    """
    level = _LOG_LEVELS.get(level_name, logging.INFO)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.setLevel(level)
            break
