from __future__ import annotations

import logging
import os
import shutil
import stat
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

import requests
from PyQt6.QtCore import QThread

from crucible.core.paths import Paths

logger = logging.getLogger(__name__)

_UMU_API_URL = "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"
_DOWNLOAD_TIMEOUT_SECS = 30
_GITHUB_API_TIMEOUT_SECS = 10
_ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}

_active_workers: set[QThread] = set()
_active_workers_lock = threading.Lock()


def register_worker(worker: QThread) -> None:
    """Add a QThread to the active worker set and connect cleanup on finished."""
    with _active_workers_lock:
        _active_workers.add(worker)
    worker.finished.connect(lambda: _cleanup_worker(worker))


def _cleanup_worker(worker: QThread) -> None:
    worker.wait()
    with _active_workers_lock:
        _active_workers.discard(worker)


def _is_supported_download_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc in _ALLOWED_DOWNLOAD_HOSTS


def _download_file(url: str, destination: Path) -> None:
    resp = requests.get(url, timeout=_DOWNLOAD_TIMEOUT_SECS, stream=True)
    try:
        resp.raise_for_status()
        expected_size = int(resp.headers.get('content-length', 0)) or None
        with destination.open('wb') as handle:
            shutil.copyfileobj(resp.raw, handle)
    finally:
        resp.close()
    if expected_size is not None:
        actual_size = destination.stat().st_size
        if actual_size != expected_size:
            destination.unlink(missing_ok=True)
            raise ValueError(
                f"Download size mismatch for {url}: expected {expected_size}, got {actual_size}"
            )


def _install_runner(download_url: str, dest: Path) -> None:
    if not _is_supported_download_url(download_url):
        raise ValueError(f"Unsupported umu-run download URL: {download_url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='umu-run.', suffix='.tmp', dir=dest.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        _download_file(download_url, tmp_path)
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise ValueError("Downloaded umu-run is empty")
        tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        tmp_path.replace(dest)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


class UmuUpdateWorker(QThread):
    """Silently ensures umu-run is present and up to date on startup."""

    def run(self) -> None:
        """Check the GitHub API for the latest umu-run release and install it if needed.

        Compares the locally cached version tag against the latest release.
        If they differ (or no local binary exists), downloads and installs
        the new binary. Errors are logged as warnings and silently swallowed.
        """
        try:
            resp = requests.get(
                _UMU_API_URL,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "crucible-launcher"},
                timeout=_GITHUB_API_TIMEOUT_SECS,
            )
            resp.raise_for_status()
            data = resp.json()

            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                logger.warning("umu-run update check: no tag_name in GitHub response")
                return

            version_file = Paths.runner_dir() / "umu-run.version"
            dest = Paths.runner_dir() / "umu-run"

            current = version_file.read_text().strip() if version_file.is_file() else ""
            if current == latest_tag and dest.is_file():
                logger.debug(f"umu-run {latest_tag} is current")
                return

            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name") == "umu-run":
                    download_url = asset.get("browser_download_url")
                    break

            if not download_url:
                logger.warning(f"umu-run: no 'umu-run' asset in release {latest_tag}")
                return

            _install_runner(download_url, dest)
            version_file.write_text(latest_tag)

            logger.info(f"umu-run updated to {latest_tag}")

        except requests.RequestException as e:
            logger.warning(f"umu-run update check failed: {e}")
        except (ValueError, OSError) as e:
            logger.warning(f"umu-run update error: {e}")
