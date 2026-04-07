from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import threading
from pathlib import Path
from typing import Callable

import requests

from crucible.core.paths import ensure_within_dir

logger = logging.getLogger(__name__)

_GITHUB_API_TIMEOUT_SECS = 10
_DOWNLOAD_STREAM_TIMEOUT_SECS = 60
_DOWNLOAD_CHUNK_SIZE = 8192


class DownloadCancelled(Exception):
    pass


class ProtonManager:
    def __init__(self) -> None:
        self.steam_dir = Path.home() / ".steam/steam"
        self.compat_dir = self.steam_dir / "compatibilitytools.d"
        self.installed = []

        self.compat_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _validate_tar_members(cls, tar: tarfile.TarFile, dest_dir: Path) -> None:
        base_dir = dest_dir.resolve()
        for member in tar.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute():
                raise ValueError(f"Archive member has absolute path: {member.name}")

            resolved_member = (base_dir / member_path).resolve()
            ensure_within_dir(base_dir, resolved_member)

            if member.issym():
                link_target = Path(member.linkname)
                if link_target.is_absolute():
                    raise ValueError(f"Archive symlink has absolute target: {member.linkname}")
                ensure_within_dir(base_dir, (resolved_member.parent / link_target).resolve())
            elif member.islnk():
                link_target = Path(member.linkname)
                if link_target.is_absolute():
                    raise ValueError(f"Archive hard link has absolute target: {member.linkname}")
                ensure_within_dir(base_dir, (base_dir / link_target).resolve())

    @classmethod
    def _extract_tarball(cls, tar_path: str | Path, dest_dir: str | Path) -> Path:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path, 'r:gz') as tar:
            cls._validate_tar_members(tar, dest_dir)
            tar.extractall(dest_dir, filter='data')

        extracted_items = list(dest_dir.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            return extracted_items[0]
        return dest_dir

    def scan_installed(self) -> list[dict[str, str]]:
        """Scan compatibilitytools.d for installed Proton versions.

        Populates ``self.installed`` with dicts containing 'name', 'path',
        and 'version' keys, sorted by name descending.

        Returns:
            List of dicts describing each installed Proton version.
        """
        self.installed = []
        for proton_dir in self.compat_dir.iterdir():
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
                'version': version
            })
        self.installed.sort(key=lambda x: x['name'], reverse=True)
        return self.installed

    def get_installed_names(self) -> list[str]:
        """Return the names of all currently installed Proton versions."""
        return [v['name'] for v in self.installed]

    def fetch_available(self) -> list[dict[str, str]]:
        """Query the GitHub API for GE-Proton releases not already installed.

        Returns:
            List of dicts with 'tag', 'name', 'url', 'published', and 'body'
            for each available release. Returns an empty list on failure.
        """
        try:
            url = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
            response = requests.get(url, timeout=_GITHUB_API_TIMEOUT_SECS)
            response.raise_for_status()
            releases = response.json()
            available = []
            for release in releases:
                tag = release['tag_name']
                if tag in self.get_installed_names():
                    continue
                assets = release.get('assets', [])
                tar_url = None
                for asset in assets:
                    if asset['name'].endswith('.tar.gz'):
                        tar_url = asset['browser_download_url']
                        break
                if tar_url:
                    available.append({
                        'tag': tag,
                        'name': release.get('name', tag),
                        'url': tar_url,
                        'published': release.get('published_at', ''),
                        'body': release.get('body', '')
                    })
            return available
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to fetch releases: {e}")
            return []

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise DownloadCancelled()

    def download_and_install(
        self,
        tag: str,
        progress_callback: Callable[[int, str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        """Download a GE-Proton tarball and install it to compatibilitytools.d.

        Fetches the release by *tag* from GitHub, streams the tar.gz asset to a
        temp file, validates the download size, extracts via a staging directory,
        and atomically moves it into place.

        Args:
            tag: GitHub release tag (e.g. ``GE-Proton9-1``).
            progress_callback: Optional ``(percent, message)`` callback for UI
                progress updates.
            cancel_event: Optional threading event; when set, the download is
                aborted and cleaned up.

        Returns:
            ``True`` if installation succeeded, ``False`` on failure or
            cancellation.
        """
        tmp_path = None
        temp_extract = None
        response = None
        try:
            self._check_cancel(cancel_event)
            url = f"https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/tags/{tag}"
            response = requests.get(url, timeout=_GITHUB_API_TIMEOUT_SECS)
            response.raise_for_status()
            release = response.json()

            tar_url = None
            for asset in release.get('assets', []):
                if asset['name'].endswith('.tar.gz'):
                    tar_url = asset['browser_download_url']
                    break
            if not tar_url:
                logger.error(f"No tar.gz asset found for {tag}")
                return False

            self._check_cancel(cancel_event)
            response = requests.get(tar_url, stream=True, timeout=_DOWNLOAD_STREAM_TIMEOUT_SECS)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                tmp_path = tmp.name
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    self._check_cancel(cancel_event)
                    if not chunk:
                        continue
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        percent = int((downloaded / total_size) * 100)
                        progress_callback(percent, f"Downloading {tag}")

            if total_size and downloaded != total_size:
                raise ValueError(
                    f"Download size mismatch for {tag}: expected {total_size}, got {downloaded}"
                )

            self._check_cancel(cancel_event)
            if progress_callback:
                progress_callback(50, f"Extracting {tag}...")

            temp_extract = tempfile.mkdtemp()
            extracted_root = self._extract_tarball(tmp_path, temp_extract)
            self._check_cancel(cancel_event)

            staged_dir = self.compat_dir / f'.{tag}.installing'
            if staged_dir.exists():
                shutil.rmtree(staged_dir, ignore_errors=True)

            staged_root = Path(temp_extract)
            if extracted_root != Path(temp_extract):
                shutil.move(str(extracted_root), str(staged_dir))
                staged_root = staged_dir
            else:
                staged_dir.mkdir()
                for item in Path(temp_extract).iterdir():
                    shutil.move(str(item), str(staged_dir / item.name))
                staged_root = staged_dir

            self._check_cancel(cancel_event)
            extract_dir = self.compat_dir / tag
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            os.replace(staged_root, extract_dir)

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
            if response is not None:
                close = getattr(response, 'close', None)
                if callable(close):
                    close()
            if tmp_path and Path(tmp_path).exists():
                os.unlink(tmp_path)
            if temp_extract and Path(temp_extract).exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
            staged_dir = self.compat_dir / f'.{tag}.installing'
            if staged_dir.exists():
                shutil.rmtree(staged_dir, ignore_errors=True)

    def delete_version(self, tag: str) -> bool:
        """Remove a Proton version directory from disk.

        Args:
            tag: Name of the Proton version to delete (directory name under
                compatibilitytools.d).

        Returns:
            ``True`` if the directory was successfully removed, ``False`` if it
            was not found or deletion failed.
        """
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
