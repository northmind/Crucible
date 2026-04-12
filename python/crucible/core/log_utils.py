"""Log access utilities — read, locate, show-in-folder, copy, upload.

Modeled after Heroic's log management:
  * Read latest log content for display in a settings/log viewer.
  * Open the log directory in the native file manager.
  * Copy raw log text to the system clipboard.
  * Upload a log to a paste service and return the URL.
"""

from __future__ import annotations

import logging
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Callable

from crucible.core.paths import Paths

logger = logging.getLogger(__name__)

# Maximum bytes read from a single log file (10 MiB, matching Heroic).
_MAX_LOG_BYTES = 10 * 1024 * 1024


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

def get_latest_log_path(game_name: str) -> Path | None:
    """Return the most-recently-modified ``.log`` file for *game_name*, or None."""
    log_dir = Paths.game_logs_dir(game_name)
    logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def get_app_log_path() -> Path | None:
    """Return the most-recently-modified Crucible application log, or None."""
    log_dir = Paths.app_logs_dir()
    logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def get_log_content(log_path: Path, max_bytes: int = _MAX_LOG_BYTES) -> str:
    """Read up to *max_bytes* from the end of *log_path*.

    Returns an empty string if the file doesn't exist or can't be read.
    """
    if not log_path or not log_path.is_file():
        return ""
    try:
        size = log_path.stat().st_size
        if size <= max_bytes:
            return log_path.read_text(errors="replace")
        with log_path.open("r", errors="replace") as fh:
            fh.seek(size - max_bytes)
            fh.readline()  # discard partial first line
            return fh.read()
    except OSError as exc:
        logger.error("Failed to read log %s: %s", log_path, exc)
        return ""


# ------------------------------------------------------------------
# Show in file manager
# ------------------------------------------------------------------

def show_log_in_folder(log_path: Path) -> bool:
    """Open the parent directory of *log_path* in the native file manager.

    Returns True if the command was launched successfully.
    """
    target = log_path if log_path.is_file() else log_path.parent
    try:
        subprocess.Popen(
            ["xdg-open", str(target.parent if target.is_file() else target)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError as exc:
        logger.error("Failed to open folder for %s: %s", log_path, exc)
        return False


# ------------------------------------------------------------------
# Clipboard
# ------------------------------------------------------------------

def copy_log_to_clipboard(log_path: Path) -> bool:
    """Copy the contents of *log_path* to the system clipboard via Qt.

    Returns True on success, False if the app instance isn't running
    or the file can't be read.
    """
    content = get_log_content(log_path)
    if not content:
        return False
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return False
        clipboard = app.clipboard()
        clipboard.setText(content)
        return True
    except Exception as exc:
        logger.error("Failed to copy log to clipboard: %s", exc)
        return False


# ------------------------------------------------------------------
# Upload to paste service
# ------------------------------------------------------------------

_PASTE_URL = "https://0x0.st"
_UPLOAD_TIMEOUT = 30  # seconds


def upload_log(log_path: Path, expire_hours: int = 24) -> str | None:
    """Upload *log_path* to 0x0.st and return the paste URL.

    Returns None on failure.
    """
    content = get_log_content(log_path)
    if not content:
        return None
    try:
        boundary = "----CrucibleLogUpload"
        filename = log_path.name
        body_parts = [
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
            f"{content}\r\n",
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="expires"\r\n\r\n'
            f"{expire_hours}\r\n",
            f"--{boundary}--\r\n",
        ]
        body = "".join(body_parts).encode("utf-8")

        req = urllib.request.Request(
            _PASTE_URL,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_UPLOAD_TIMEOUT) as resp:
            url = resp.read().decode("utf-8").strip()
            if url.startswith("http"):
                return url
            logger.warning("Unexpected response from paste service: %s", url)
            return None
    except Exception as exc:
        logger.error("Failed to upload log %s: %s", log_path, exc)
        return None
