from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from crucible.ui.artwork_fetcher import _ArtworkFetcher

logger = logging.getLogger(__name__)

# Tags for the internal _fetch_done signal's extra field, replacing
# fragile content-sniffing with explicit type markers.
_TAG_NAME = 'name:'
_TAG_DIR = 'dir:'


class ArtworkManager(QObject):
    artwork_ready        = pyqtSignal(str, QPixmap)
    name_fetched         = pyqtSignal(str, str)
    install_dir_resolved = pyqtSignal(str, str)
    _fetch_done          = pyqtSignal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._fetcher = _ArtworkFetcher()
        self._fetch_done.connect(self._on_fetch_done)
        self._in_flight: set[str] = set()
        self._in_flight_lock = threading.Lock()

    def _has_cached_art(self, exe_path: str = '', app_id: str | None = None, game_name: str = '') -> str:
        """Return the cached artwork path string if a valid image exists, else ''."""
        path = self._fetcher.get_artwork_path(exe_path=exe_path, app_id=app_id, game_name=game_name)
        if path.exists() and path.suffix == '.jpg':
            return str(path)
        return ''

    @staticmethod
    def _lookup_key(game_name: str, exe_path: str = '', app_id: str | None = None) -> str:
        if app_id:
            return f'app:{app_id}'
        if exe_path:
            return f'exe:{exe_path.strip().lower()}'
        return f'name:{game_name.strip().lower()}'

    def _do_fetch_guarded(self, key: str, game_name: str, exe_path: str, app_id: str | None) -> None:
        try:
            self._do_fetch(game_name, exe_path, app_id)
        finally:
            with self._in_flight_lock:
                self._in_flight.discard(key)

    def fetch_artwork(self, game_name: str, exe_path: str = '', app_id: str | None = None) -> None:
        """Fetch artwork for a game, emitting artwork_ready when available.

        Returns immediately if a cached image exists. Otherwise starts a
        background thread to search Steam and download the header image.
        """
        cached = self._has_cached_art(exe_path, app_id, game_name)
        if cached:
            self._on_fetch_done(game_name, cached, '')
            return

        key = self._lookup_key(game_name, exe_path, app_id)
        with self._in_flight_lock:
            if key in self._in_flight:
                return
            self._in_flight.add(key)

        threading.Thread(
            target=self._do_fetch_guarded,
            args=(key, game_name, exe_path, app_id),
            daemon=True,
        ).start()

    def _do_fetch(self, game_name: str, exe_path: str, app_id: str | None) -> None:
        # No cached-art re-check here: the _in_flight guard in fetch_artwork()
        # already prevents duplicate fetches for the same game, so any artwork
        # that lands between the caller's check and this point will simply be
        # overwritten with an identical file.
        search_name = None
        if not app_id and exe_path:
            app_id = self._fetcher.cached_app_id(exe_path, game_name)
            if not app_id:
                app_id, search_name = self._fetcher.find_app_match_by_exe_name(exe_path, game_name)

        if search_name and search_name != game_name:
            self._fetch_done.emit(game_name, '', f'{_TAG_NAME}{search_name}')
            game_name = search_name

        if app_id:
            self._fetcher.cache_app_id(app_id, exe_path, game_name)
            if exe_path:
                install_dir = self._fetcher.resolve_install_dir(app_id, exe_path)
                if install_dir:
                    self._fetch_done.emit(game_name, '', f'{_TAG_DIR}{install_dir}')

        path = self._fetcher.get_artwork_path(exe_path=exe_path, app_id=app_id, game_name=game_name)

        if path.exists() and path.suffix == '.jpg':
            self._fetch_done.emit(game_name, str(path), '')
            return

        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.debug(f"Failed to remove stale artwork file {path}: {exc}")

        if app_id:
            header_url, steam_name = self._fetcher.fetch_header_url_from_steam_api(app_id)
            if steam_name and steam_name != game_name:
                self._fetch_done.emit(game_name, '', f'{_TAG_NAME}{steam_name}')
                game_name = steam_name
            if header_url and self._fetcher.download_image(header_url, path):
                self._fetch_done.emit(game_name, str(path), '')
                return

            fallback_urls = [
                f'https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg',
                f'https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg',
            ]
            for url in fallback_urls:
                if self._fetcher.download_image(url, path):
                    self._fetch_done.emit(game_name, str(path), '')
                    return

        self._fetch_done.emit(game_name, '', '')

    def _on_fetch_done(self, game_name: str, path_str: str, extra: str) -> None:
        if not path_str and extra:
            if extra.startswith(_TAG_DIR):
                self.install_dir_resolved.emit(game_name, extra[len(_TAG_DIR):])
            elif extra.startswith(_TAG_NAME):
                self.name_fetched.emit(game_name, extra[len(_TAG_NAME):])
            return

        if path_str:
            pixmap = QPixmap(path_str)
            if not pixmap.isNull() and pixmap.width() > 50:
                self.artwork_ready.emit(game_name, pixmap)
                return

        placeholder = QPixmap(230, 108)
        placeholder.fill(Qt.GlobalColor.gray)
        self.artwork_ready.emit(game_name, placeholder)
