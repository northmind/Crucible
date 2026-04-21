"""Artwork fetching and caching for the game library.

Handles artwork file paths, image downloads, and the app-ID index that
maps local executables / game names to Steam app IDs.  All Steam
interaction (search, SteamCMD, appdetails) is delegated to
:class:`~crucible.ui.steam_api.SteamAPI`.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

from crucible.core.paths import Paths, artwork_safe_name
from crucible.ui.steam_api import SteamAPI

logger = logging.getLogger(__name__)


class _ArtworkFetcher:
    """Artwork storage, download, and app-ID caching.

    Keeps a thin app-ID index so repeat lookups for the same executable
    or game name skip the Steam search entirely.
    """

    def __init__(self) -> None:
        self.artwork_dir = Paths.artwork_dir()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Crucible Launcher/1.0',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://store.steampowered.com/',
        })
        self.steam = SteamAPI(self.session)
        self._appid_index: dict[str, str] = {}

    # ------------------------------------------------------------------
    # App-ID index  (local cache keyed on exe path / game name)
    # ------------------------------------------------------------------

    @staticmethod
    def _key_for_path(exe_path: str) -> str:
        return f'path:{exe_path.strip().lower()}'

    @staticmethod
    def _key_for_game(game_name: str) -> str:
        return f'name:{game_name.strip().lower()}'

    def cache_app_id(self, app_id: str, exe_path: str = '', game_name: str = '') -> None:
        """Store *app_id* in the in-memory index for later fast lookup."""
        if exe_path:
            self._appid_index[self._key_for_path(exe_path)] = app_id
        if game_name:
            self._appid_index[self._key_for_game(game_name)] = app_id

    def cached_app_id(self, exe_path: str = '', game_name: str = '') -> str | None:
        """Return a previously cached app ID, or ``None``."""
        if exe_path:
            hit = self._appid_index.get(self._key_for_path(exe_path))
            if hit:
                return hit
        if game_name:
            return self._appid_index.get(self._key_for_game(game_name))
        return None

    # ------------------------------------------------------------------
    # Delegated Steam methods  (keep ArtworkManager's call-sites stable)
    # ------------------------------------------------------------------

    def find_app_match_by_exe_name(
        self, exe_path: str, game_name: str = '',
    ) -> tuple[str | None, str | None]:
        return self.steam.find_app_match_by_exe_name(exe_path, game_name)

    def resolve_install_dir(self, app_id: str, actual_exe_path: str) -> str | None:
        return self.steam.resolve_install_dir(app_id, actual_exe_path)

    def fetch_header_url_from_steam_api(self, app_id: str) -> tuple[str | None, str | None]:
        return self.steam.fetch_header_url(app_id)

    # ------------------------------------------------------------------
    # Artwork file paths
    # ------------------------------------------------------------------

    @staticmethod
    def _artwork_key(exe_path: str, app_id: str | None, game_name: str) -> str:
        if exe_path:
            digest = hashlib.sha1(exe_path.strip().lower().encode('utf-8')).hexdigest()[:16]
            return f'exe_{digest}'
        if app_id:
            return f'app_{app_id}'
        return artwork_safe_name(game_name)

    def get_game_artwork_dir(
        self, exe_path: str = '', app_id: str | None = None, game_name: str = '',
    ) -> Path:
        """Return the per-game artwork directory."""
        key = self._artwork_key(exe_path, app_id, game_name)
        return self.artwork_dir / key

    def get_artwork_path(
        self, exe_path: str = '', app_id: str | None = None, game_name: str = '',
        variant: str = '',
    ) -> Path:
        """Return the local filesystem path where artwork is stored.

        Each game gets its own subdirectory under the artwork root.

        *variant* selects the artwork type:
        - ``''``        — header (460x215, default)
        - ``'portrait'``— library capsule (600x900)
        - ``'hero'``    — library hero banner (~1920x620)
        """
        game_dir = self.get_game_artwork_dir(exe_path, app_id, game_name)
        filename = variant if variant else 'header'
        return game_dir / f'{filename}.jpg'

    # ------------------------------------------------------------------
    # Image download
    # ------------------------------------------------------------------

    def download_image(self, url: str, save_path: Path) -> bool:
        """Download an image from *url* and write it to *save_path*.

        Returns ``True`` on success, ``False`` on any failure.
        """
        try:
            resp = self.session.get(url, timeout=4)
            if resp.status_code == 200 and len(resp.content) > 1000:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(resp.content)
                return True
            logger.debug(
                "Artwork download returned status %s or too little data for %s",
                resp.status_code, url,
            )
        except requests.RequestException as exc:
            logger.debug("Artwork download failed for %s: %s", url, exc)
        except OSError as exc:
            logger.debug("Failed to write artwork to %s: %s", save_path, exc)
        return False
