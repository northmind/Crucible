from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Callable

import requests

from crucible.core.tar_utils import extract_tarball
from crucible.core.workers import _is_supported_download_url

logger = logging.getLogger(__name__)

_GITHUB_API_TIMEOUT_SECS = 10
_DOWNLOAD_STREAM_TIMEOUT_SECS = 60
_DOWNLOAD_CHUNK_SIZE = 8192

SOURCES: dict[str, dict[str, str]] = {
    "ge": {
        "repo": "GloriousEggroll/proton-ge-custom",
        "asset_suffix": ".tar.gz",
        "prefix": "GE-Proton",
    },
    "umu": {
        "repo": "Open-Wine-Components/umu-proton",
        "asset_suffix": ".tar.gz",
        "prefix": "UMU-Proton",
    },
    "cachy": {
        "repo": "CachyOS/proton-cachyos",
        "asset_suffix": "-x86_64.tar.xz",
        "prefix": "cachyos-",
    },
}


class DownloadCancelled(Exception):
    pass


class ProtonManager:
    def __init__(self) -> None:
        self.steam_dir = Path.home() / ".steam/steam"
        self.compat_dir = self.steam_dir / "compatibilitytools.d"
        self.installed = []
        self._extra_dirs: list[Path] = []

        self.compat_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _guess_source(name: str) -> str:
        """Guess which source a runner belongs to based on its directory name."""
        lower = name.lower()
        if lower.startswith("ge-proton"):
            return "ge"
        if lower.startswith("umu-proton"):
            return "umu"
        if "cachyos" in lower or lower.startswith("proton-cachyos") or lower.startswith("cachyos"):
            return "cachy"
        return "ge"

    def add_search_dir(self, path: Path) -> None:
        if path not in self._extra_dirs:
            self._extra_dirs.append(path)

    def set_search_dirs(self, paths: list[Path]) -> None:
        self._extra_dirs = []
        for path in paths:
            self.add_search_dir(path)

    def scan_installed(self) -> list[dict[str, str]]:
        """Scan compatibilitytools.d for installed Proton versions."""
        self.installed = []
        scan_dirs = [self.compat_dir] + [d for d in self._extra_dirs if d.is_dir()]
        for scan_dir in scan_dirs:
            for proton_dir in scan_dir.iterdir():
                if not proton_dir.is_dir():
                    continue
                if not (proton_dir / "proton").exists():
                    continue
                name = proton_dir.name
                version = "unknown"
                version_file = proton_dir / "version"
                if version_file.exists():
                    version = version_file.read_text().strip()
                elif (proton_dir / "VERSION").exists():
                    version = (proton_dir / "VERSION").read_text().strip()
                self.installed.append({
                    'name': name,
                    'path': str(proton_dir),
                    'version': version,
                    'source': self._guess_source(name),
                })
        self.installed.sort(key=lambda x: x['name'], reverse=True)
        return self.installed

    def get_installed_names(self) -> list[str]:
        return [v['name'] for v in self.installed]

    def fetch_releases(self, source: str = "ge") -> list[dict[str, str]]:
        """Query GitHub API for releases from the given source."""
        src = SOURCES.get(source)
        if not src:
            logger.error(f"Unknown source: {source}")
            return []
        try:
            url = f"https://api.github.com/repos/{src['repo']}/releases"
            response = requests.get(url, timeout=_GITHUB_API_TIMEOUT_SECS)
            response.raise_for_status()
            releases = response.json()
            result = []
            for release in releases:
                tag = release['tag_name']
                assets = release.get('assets', [])
                tar_url = None
                tar_size = 0
                for asset in assets:
                    if asset['name'].endswith(src['asset_suffix']):
                        tar_url = asset['browser_download_url']
                        tar_size = asset.get('size', 0)
                        break
                if tar_url:
                    result.append({
                        'tag': tag,
                        'name': release.get('name', tag),
                        'url': tar_url,
                        'published': release.get('published_at', ''),
                        'body': release.get('body', ''),
                        'size': tar_size,
                        'source': source,
                    })
            return result
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to fetch releases: {e}")
            return []

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise DownloadCancelled()

    def _download_tarball(
        self,
        tag: str,
        src: dict[str, str],
        cancel_event: threading.Event | None,
        progress_callback: Callable[[int, str], None] | None,
    ) -> tuple[str, str]:
        """Download a release tarball, returning (tar_url, tmp_path).

        Raises DownloadCancelled, requests.RequestException, or ValueError.
        """
        self._check_cancel(cancel_event)
        url = f"https://api.github.com/repos/{src['repo']}/releases/tags/{tag}"
        resp = requests.get(url, timeout=_GITHUB_API_TIMEOUT_SECS)
        resp.raise_for_status()
        release = resp.json()

        tar_url = None
        for asset in release.get('assets', []):
            if asset['name'].endswith(src['asset_suffix']):
                tar_url = asset['browser_download_url']
                break
        if not tar_url:
            raise ValueError(f"No {src['asset_suffix']} asset found for {tag}")
        if not _is_supported_download_url(tar_url):
            raise ValueError(f"Unsupported Proton download URL: {tar_url}")

        self._check_cancel(cancel_event)
        is_xz = src['asset_suffix'].endswith('.tar.xz')
        suffix = '.tar.xz' if is_xz else '.tar.gz'

        response = requests.get(tar_url, stream=True, timeout=_DOWNLOAD_STREAM_TIMEOUT_SECS)
        try:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    self._check_cancel(cancel_event)
                    if not chunk:
                        continue
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        percent = int((downloaded / total_size) * 70)
                        progress_callback(percent, f"Downloading {tag}")
        finally:
            response.close()

        if total_size and downloaded != total_size:
            os.unlink(tmp_path)
            raise ValueError(
                f"Download size mismatch for {tag}: expected {total_size}, got {downloaded}"
            )
        return tar_url, tmp_path

    def _stage_and_install(
        self,
        tag: str,
        tmp_path: str,
        cancel_event: threading.Event | None,
        progress_callback: Callable[[int, str], None] | None,
    ) -> None:
        """Extract tarball, stage into compat_dir, and atomically install.

        Uses a UUID-based staging directory to prevent collisions with
        concurrent downloads of the same tag.

        Raises DownloadCancelled, OSError, tarfile.TarError.
        """
        self._check_cancel(cancel_event)
        if progress_callback:
            progress_callback(70, f"Extracting {tag}...")

        temp_extract = tempfile.mkdtemp()
        # Unique staging name prevents races with concurrent downloads
        staging_name = f'.{tag}.{uuid.uuid4().hex[:8]}.installing'
        staged_dir = self.compat_dir / staging_name
        try:
            extracted_root = extract_tarball(tmp_path, temp_extract)
            self._check_cancel(cancel_event)

            if progress_callback:
                progress_callback(85, f"Installing {tag}...")

            if extracted_root != Path(temp_extract):
                shutil.move(str(extracted_root), str(staged_dir))
            else:
                staged_dir.mkdir()
                for item in Path(temp_extract).iterdir():
                    shutil.move(str(item), str(staged_dir / item.name))

            self._check_cancel(cancel_event)
            extract_dir = self.compat_dir / tag
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            os.replace(staged_dir, extract_dir)
        finally:
            shutil.rmtree(temp_extract, ignore_errors=True)
            if staged_dir.exists():
                shutil.rmtree(staged_dir, ignore_errors=True)

    def download_and_install(
        self,
        tag: str,
        progress_callback: Callable[[int, str], None] | None = None,
        cancel_event: threading.Event | None = None,
        source: str = "ge",
    ) -> bool:
        """Download and install a Proton tarball from the given source."""
        src = SOURCES.get(source)
        if not src:
            logger.error(f"Unknown source: {source}")
            return False

        tmp_path = None
        try:
            _, tmp_path = self._download_tarball(
                tag, src, cancel_event, progress_callback,
            )
            self._stage_and_install(
                tag, tmp_path, cancel_event, progress_callback,
            )
            if progress_callback:
                progress_callback(100, f"Installed {tag}")
            self.scan_installed()
            return True
        except DownloadCancelled:
            logger.info(f"Cancelled Proton install for {tag}")
            return False
        except (requests.RequestException, OSError, ValueError, tarfile.TarError) as e:
            logger.error(f"Failed to download {tag}: {e}")
            return False
        finally:
            if tmp_path and Path(tmp_path).exists():
                os.unlink(tmp_path)

    def delete_version(self, tag: str) -> bool:
        proton_dir = self.compat_dir / tag
        if not proton_dir.exists():
            logger.error(f"Proton version not found: {tag}")
            return False
        try:
            shutil.rmtree(proton_dir)
            self.scan_installed()
            return True
        except OSError as e:
            logger.error(f"Failed to delete {tag}: {e}")
            return False
