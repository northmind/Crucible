"""Steam API client for game identification and install-directory resolution.

Delegates to the Steam store search, SteamCMD PICS API, and appdetails.
"""

from __future__ import annotations

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from crucible.core.paths import GENERIC_DIRS

logger = logging.getLogger(__name__)


class SteamAPI:
    """Stateful client for Steam game identification."""

    _STEAMCMD_URL = 'https://api.steamcmd.net/v1/info/{app_id}'

    # Minimum cumulative score a candidate must reach to be accepted.
    _MIN_CONFIDENCE = 3

    def __init__(self, session: requests.Session) -> None:
        self._session = session
        self._steamcmd_cache: dict[str, dict | None] = {}
        # _appdetails_cache is only accessed from a single background thread
        # per game (serialised by artwork_manager._in_flight), so no lock is
        # needed — unlike _steamcmd_cache which is hit from parallel scoring
        # threads and therefore protected by _cache_lock.
        self._appdetails_cache: dict[str, dict] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def normalize_name(value: str) -> str:
        """Collapse *value* to lowercase alphanumeric tokens."""
        return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()

    @classmethod
    def _ancestor_search_terms(cls, exe_path: str, max_depth: int = 8) -> list[str]:
        """Collect non-generic ancestor directory names as search terms."""
        terms: list[str] = []
        current = Path(exe_path).parent
        for _ in range(max_depth):
            if current == current.parent:
                break
            name = current.name
            if name and name.lower() not in GENERIC_DIRS:
                readable = re.sub(r'[_.-]+', ' ', name).strip()
                if readable and len(readable) > 2:
                    terms.append(readable)
            current = current.parent
        return terms

    @staticmethod
    def exe_candidates(exe_path: str, game_name: str) -> tuple[list[str], str | None]:
        """Derive de-duplicated search terms and the exe basename from paths."""
        exe_name: str | None = None
        terms: list[str] = []

        if exe_path:
            exe_name = Path(exe_path).name
            stem = Path(exe_path).stem
            if stem:
                terms.append(stem)
                normalized = re.sub(r'[_\\.-]+', ' ', stem).strip()
                if normalized and normalized.lower() != stem.lower():
                    terms.append(normalized)

        if game_name:
            terms.append(game_name)

        if exe_path:
            terms.extend(SteamAPI._ancestor_search_terms(exe_path))

        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            cleaned = term.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped, exe_name

    _STORE_SEARCH_URL = 'https://store.steampowered.com/api/storesearch/'

    def search_candidates(self, query: str, limit: int = 10) -> list[tuple[str, str]]:
        """Search the Steam store for *query*, returning ``(app_id, title)`` pairs."""
        try:
            resp = self._session.get(
                self._STORE_SEARCH_URL,
                params={'term': query, 'l': 'english', 'cc': 'US'},
                timeout=3,
            )
            resp.raise_for_status()
            items = resp.json().get('items', [])
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Steam search failed for query '%s': %s", query, exc)
            return []

        candidates: list[tuple[str, str]] = []
        for item in items[:limit]:
            app_id = str(item.get('id', ''))
            name = item.get('name', '').strip()
            if app_id and name:
                candidates.append((app_id, name))
        return candidates

    def fetch_steamcmd_config(self, app_id: str) -> dict | None:
        """Fetch the full app record from the SteamCMD API (thread-safe, cached)."""
        with self._cache_lock:
            if app_id in self._steamcmd_cache:
                return self._steamcmd_cache[app_id]
        url = self._STEAMCMD_URL.format(app_id=app_id)
        try:
            resp = self._session.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                app_data = data.get('data', {}).get(str(app_id))
                if app_data and isinstance(app_data, dict):
                    with self._cache_lock:
                        self._steamcmd_cache[app_id] = app_data
                    return app_data
        except requests.RequestException as exc:
            logger.debug("SteamCMD API request failed for app %s: %s", app_id, exc)
        except (ValueError, AttributeError) as exc:
            logger.debug("SteamCMD API response parse error for app %s: %s", app_id, exc)
        with self._cache_lock:
            self._steamcmd_cache[app_id] = None
        return None

    @staticmethod
    def launch_executables(app_data: dict) -> list[str]:
        """Extract all launch executable filenames (lowered) from SteamCMD data."""
        launch = app_data.get('config', {}).get('launch', {})
        names: list[str] = []
        for entry in (launch if isinstance(launch, list) else launch.values()):
            exe = entry.get('executable', '') if isinstance(entry, dict) else ''
            if exe:
                name = exe.replace('\\', '/').rsplit('/', 1)[-1].lower()
                if name:
                    names.append(name)
        return names

    def _score_candidate(
        self, app_id: str, app_name: str,
        exe_name_lower: str, exe_path_lower: str,
        normalized_stem: str, normalized_game: str,
    ) -> int:
        """Score a candidate: +10 launch-exe, +6 installdir, +4 exact name, +2 substring."""
        score = 0
        app_data = self.fetch_steamcmd_config(app_id)

        if app_data:
            if exe_name_lower in self.launch_executables(app_data):
                score += 10

            installdir = app_data.get('config', {}).get('installdir', '')
            if installdir and isinstance(installdir, str):
                installdir_lower = installdir.strip().lower()
                if installdir_lower and f'/{installdir_lower}/' in exe_path_lower:
                    score += 6

        title_norm = self.normalize_name(app_name)
        is_addon = any(tag in title_norm for tag in (
            ' dlc', ' demo', ' soundtrack', ' ost', ' season pass',
        ))

        if title_norm == normalized_stem or (normalized_game and title_norm == normalized_game):
            score += 4
        elif not is_addon and normalized_stem and normalized_stem in title_norm:
            score += 2

        return score

    _IO_WORKERS = 6

    def find_app_match_by_exe_name(
        self, exe_path: str, game_name: str = '',
    ) -> tuple[str | None, str | None]:
        """Return ``(app_id, app_name)`` for the best match, or ``(None, None)``."""
        terms, exe_name = self.exe_candidates(exe_path, game_name)
        if not terms or not exe_name:
            return None, None

        exe_name_lower = exe_name.lower()
        exe_path_lower = f'/{exe_path.strip().replace(chr(92), "/").lower()}/'
        normalized_stem = self.normalize_name(Path(exe_name).stem)
        normalized_game = self.normalize_name(game_name)

        # Parallel search across all terms.
        all_candidates: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        with ThreadPoolExecutor(max_workers=self._IO_WORKERS) as pool:
            futures = {pool.submit(self.search_candidates, t): t for t in terms}
            for future in as_completed(futures):
                for app_id, app_name in future.result():
                    if app_id not in seen_ids:
                        seen_ids.add(app_id)
                        all_candidates.append((app_id, app_name))

        if not all_candidates:
            return None, None

        # Perfect score (launch-exe 10 + installdir 6) triggers early exit.
        _PERFECT_SCORE = 16
        best_score = 0
        best: tuple[str, str] | None = None

        with ThreadPoolExecutor(max_workers=self._IO_WORKERS) as pool:
            score_futures = {
                pool.submit(
                    self._score_candidate,
                    app_id, app_name, exe_name_lower, exe_path_lower,
                    normalized_stem, normalized_game,
                ): (app_id, app_name)
                for app_id, app_name in all_candidates
            }
            for future in as_completed(score_futures):
                app_id, app_name = score_futures[future]
                score = future.result()
                if score > best_score:
                    best_score = score
                    best = (app_id, app_name)
                if best_score >= _PERFECT_SCORE:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

        if best and best_score >= self._MIN_CONFIDENCE:
            return best
        return None, None

    def fetch_appdetails(self, app_id: str) -> dict | None:
        """Fetch the Steam Store ``appdetails`` for *app_id* (cached)."""
        if app_id in self._appdetails_cache:
            return self._appdetails_cache[app_id]
        url = f'https://store.steampowered.com/api/appdetails?appids={app_id}'
        try:
            resp = self._session.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                app_data = data.get(str(app_id), {})
                if app_data.get('success'):
                    result = app_data.get('data', {})
                    self._appdetails_cache[app_id] = result
                    return result
        except requests.RequestException as exc:
            logger.debug("Steam appdetails request failed for app %s: %s", app_id, exc)
        except ValueError as exc:
            logger.debug("Steam appdetails JSON parse failed for app %s: %s", app_id, exc)
        return None

    def fetch_header_url(self, app_id: str) -> tuple[str | None, str | None]:
        """Return ``(header_image_url, steam_name)`` from appdetails."""
        game_data = self.fetch_appdetails(app_id)
        if game_data:
            header = game_data.get('header_image')
            steam_name = game_data.get('name')
            if header:
                return header.split('?')[0], steam_name
        return None, None

    @staticmethod
    def find_ancestor_by_name(exe_path: Path, folder_name: str) -> Path | None:
        """Walk up from *exe_path* and return the first ancestor matching *folder_name*."""
        target = folder_name.lower()
        current = exe_path.parent
        while current != current.parent:
            if current.name.lower() == target:
                return current
            current = current.parent
        return None

    def resolve_install_dir(self, app_id: str, actual_exe_path: str) -> str | None:
        """Resolve the game install root using the Steam ``installdir`` value."""
        app_data = self.fetch_steamcmd_config(app_id)
        installdir = (
            app_data.get('config', {}).get('installdir')
            if app_data else None
        )
        if not installdir or not isinstance(installdir, str):
            return None
        root = self.find_ancestor_by_name(Path(actual_exe_path), installdir.strip())
        if root and root.is_dir():
            return str(root)
        return None
