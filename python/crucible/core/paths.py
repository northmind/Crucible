from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_GAME_SUBDIR_NAMES = frozenset((
    "binaries", "bin", "win64", "win32", "x64", "x86", "x86_64", "windows",
    "engine", "game", "content", "app", "apps",
    "build", "shipping", "development", "programs",
))

# Superset of _GAME_SUBDIR_NAMES that also includes Steam library path
# segments and OS-level directories.  Used by steam_api._ancestor_search_terms
# to filter non-game-specific ancestor directory names from search queries.
GENERIC_DIRS: frozenset[str] = _GAME_SUBDIR_NAMES | frozenset((
    "program files", "program files (x86)", "steamapps", "common",
    "games", "steam", "library",
))


_MAX_GAME_ROOT_DEPTH = 16
_MAX_APPID_SEARCH_DEPTH = 10


def find_game_root(exe_path: str) -> str | None:
    """Walk up from *exe_path*, skipping known build/engine subdirs, to find the game root.

    Args:
        exe_path: Absolute path to the game executable.

    Returns:
        The game root directory as a string, or ``None`` if *exe_path* is
        invalid or the root cannot be determined within *_MAX_GAME_ROOT_DEPTH*
        levels.
    """
    if not exe_path or not Path(exe_path).exists():
        return None
    current = Path(exe_path).parent
    for _ in range(_MAX_GAME_ROOT_DEPTH):
        if current == current.parent:
            break
        if current.name.lower() in _GAME_SUBDIR_NAMES:
            current = current.parent
            continue
        return str(current)
    return None


def find_app_id_in_game_dir(game_root: str) -> str | None:
    """Search *game_root* for a ``steam_appid.txt`` file and return its numeric contents.

    Walks the directory tree up to *_MAX_APPID_SEARCH_DEPTH* levels deep.

    Args:
        game_root: Absolute path to the game root directory.

    Returns:
        The Steam app ID string if found, or ``None`` if the file is missing,
        unreadable, or does not contain a numeric ID.
    """
    if not game_root or not Path(game_root).exists():
        return None
    sep_count = game_root.count(os.sep)
    for root, dirs, files in os.walk(game_root, topdown=True, followlinks=False):
        if "steam_appid.txt" in files:
            try:
                with open(Path(root) / "steam_appid.txt") as f:
                    app_id = f.read().strip()
                    if app_id.isdigit():
                        return app_id
            except OSError as exc:
                logger.debug(f"Failed to read steam_appid.txt under {root}: {exc}")
        if root.count(os.sep) - sep_count >= _MAX_APPID_SEARCH_DEPTH:
            dirs.clear()
    return None


_APPIMAGE_KEYS = (
    'LD_LIBRARY_PATH', 'LD_PRELOAD',
    'PYTHONHOME', 'PYTHONPATH',
    'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH',
    'QT_QPA_FONTDIR', 'QTDIR', 'QT_XKB_CONFIG_ROOT',
)
_APPIMAGE_IDENTITY_KEYS = (
    'APPIMAGE', 'APPDIR', 'OWD', 'ARGV0',
)
_DESKTOP_LAUNCH_KEYS = (
    'DESKTOP_STARTUP_ID', 'XDG_ACTIVATION_TOKEN',
    'BAMF_DESKTOP_FILE_HINT',
    'GIO_LAUNCHED_DESKTOP_FILE', 'GIO_LAUNCHED_DESKTOP_FILE_PID',
)
# Keys saved by AppRun as CRUCIBLE_ORIG_<KEY> before AppImage overrides them.
_APPIMAGE_SAVED_KEYS = (
    'LD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH',
    'QT_PLUGIN_PATH', 'PATH',
)


def _is_appimage() -> bool:
    """Return True if running inside an AppImage (APPDIR is set)."""
    return 'APPDIR' in os.environ


def _restore_or_remove(env: dict[str, str], key: str) -> None:
    """Restore *key* from its ``CRUCIBLE_ORIG_`` backup, or remove it entirely."""
    orig_key = f'CRUCIBLE_ORIG_{key}'
    orig_val = env.get(orig_key, '')
    if orig_val:
        env[key] = orig_val
    else:
        env.pop(key, None)
    env.pop(orig_key, None)


def clean_env() -> dict[str, str]:
    """Return a copy of ``os.environ`` suitable for launching child tools.

    In AppImage mode the bundled ``PYTHONHOME``, ``PYTHONPATH``,
    ``QT_PLUGIN_PATH`` and ``LD_LIBRARY_PATH`` are restored to their
    pre-AppImage values (saved by ``AppRun`` as ``CRUCIBLE_ORIG_*``).
    AppImage identity vars (``APPDIR``, ``APPIMAGE``, ``OWD``) are removed.
    """
    env = os.environ.copy()
    if _is_appimage():
        for key in _APPIMAGE_SAVED_KEYS:
            _restore_or_remove(env, key)
    for key in _APPIMAGE_KEYS:
        if key not in _APPIMAGE_SAVED_KEYS:
            env.pop(key, None)
    for key in ('APPDIR', 'APPIMAGE', 'OWD'):
        env.pop(key, None)
    return env


def display_name_from_exe(exe_path: str) -> str:
    """Derive a human-readable display name from an executable path.

    Replaces underscores and hyphens with spaces, then capitalises each word.
    """
    stem = Path(exe_path).stem
    return ' '.join(word.capitalize() for word in stem.replace('_', ' ').replace('-', ' ').split())


def safe_name(name: str) -> str:
    """Convert *name* to a lowercase identifier with non-alphanumeric runs replaced by underscores."""
    return re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')


def artwork_safe_name(name: str) -> str:
    """Convert *name* to an artwork-safe filename by replacing spaces/slashes and stripping punctuation."""
    return name.replace(' ', '_').replace('/', '_').replace(':', '').replace('"', '').replace('?', '')


def strip_launch_env(env: dict[str, str]) -> None:
    """Remove desktop-launch and AppImage variables from *env* in place.

    In AppImage mode, ``CRUCIBLE_ORIG_*`` values (saved by ``AppRun``) are
    restored so child processes (games, umu-run) see the user's original
    environment rather than the AppImage's bundled paths.
    """
    for key in _DESKTOP_LAUNCH_KEYS + _APPIMAGE_IDENTITY_KEYS:
        env.pop(key, None)
    if _is_appimage():
        for key in _APPIMAGE_SAVED_KEYS:
            _restore_or_remove(env, key)
        # Remove remaining AppImage-only vars not in _APPIMAGE_SAVED_KEYS
        for key in _APPIMAGE_KEYS:
            if key not in _APPIMAGE_SAVED_KEYS:
                env.pop(key, None)
    # Clean up any leftover CRUCIBLE_ORIG_ keys
    for key in list(env):
        if key.startswith('CRUCIBLE_ORIG_'):
            del env[key]


def ensure_within_dir(base_dir: Path, candidate: Path) -> None:
    """Raise ValueError if *candidate* is not under *base_dir*."""
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"Archive member escapes destination: {candidate}") from exc


class Paths:
    @classmethod
    def data_dir(cls) -> Path:
        """Return ``~/.local/share/crucible-launcher/``, creating it if needed."""
        data = Path.home() / ".local" / "share" / "crucible-launcher"
        data.mkdir(parents=True, exist_ok=True)
        return data

    @classmethod
    def logs_dir(cls) -> Path:
        """Return the top-level logs directory, creating it if needed."""
        logs = cls.data_dir() / "logs"
        logs.mkdir(exist_ok=True)
        return logs


    @classmethod
    def app_logs_dir(cls) -> Path:
        """Return the application log directory (``logs/app/``), creating it if needed."""
        logs = cls.logs_dir() / 'app'
        logs.mkdir(parents=True, exist_ok=True)
        return logs

    @classmethod
    def game_logs_dir(cls, game_name: str) -> Path:
        """Return the per-game log directory (``logs/games/<safe_name>/``), creating it if needed."""
        logs = cls.logs_dir() / 'games' / safe_name(game_name)
        logs.mkdir(parents=True, exist_ok=True)
        return logs

    @classmethod
    def artwork_dir(cls) -> Path:
        """Return the artwork cache directory, creating it if needed."""
        artwork = cls.data_dir() / "artwork"
        artwork.mkdir(exist_ok=True)
        return artwork

    @classmethod
    def runner_dir(cls) -> Path:
        """Return the runner/proton storage directory, creating it if needed."""
        runner = cls.data_dir() / "runner"
        runner.mkdir(exist_ok=True)
        return runner
