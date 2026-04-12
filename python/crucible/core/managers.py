from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from crucible.core.fingerprint import FingerprintManager
from crucible.core.events import event_bus
from crucible.core.game_lifecycle import GameLifecycleMixin
from crucible.core.game_utils import _build_dll_overrides, _load_json_file, _write_json_file
from crucible.core.global_config import GlobalConfig
from crucible.core.launcher import GameLauncher
from crucible.core.types import GameDict
from crucible.core.paths import (
    Paths,
    find_game_root,
    safe_name,
)

logger = logging.getLogger(__name__)


class GameManager(GameLifecycleMixin):
    def __init__(self) -> None:
        self.data_dir = Paths.data_dir()
        self.games_dir = self.data_dir / "games"
        self.prefixes_dir = self.data_dir / "Prefix"
        self.games = []
        self.fingerprint = FingerprintManager(self.data_dir / 'fingerprints')
        self.global_config = GlobalConfig()

        self.games_dir.mkdir(exist_ok=True)
        self.prefixes_dir.mkdir(exist_ok=True)

        self.launcher = GameLauncher(self)

    # Static method wrappers — delegate to game_utils for backward compat
    _build_dll_overrides = staticmethod(_build_dll_overrides)
    _load_json_file = staticmethod(_load_json_file)
    _write_json_file = staticmethod(_write_json_file)

    def _load_game_record(self, game_file: Path) -> dict[str, Any]:
        return self._load_json_file(game_file)

    def _write_game_record(self, game_file: Path, data: dict[str, Any]) -> None:
        self._write_json_file(game_file, data)

    def _update_game_record(self, game_file: Path, updates: dict[str, Any]) -> bool:
        try:
            data = self._load_game_record(game_file)
            data.update(updates)
            self._write_game_record(game_file, data)
            self.scan_games()
            game_name = data.get('name', '')
            if game_name:
                event_bus.game_updated.emit(game_name)
            return True
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error(f"Failed to update game record {game_file}: {exc}")
            return False

    def _delete_paths(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                logger.error(f"Failed to delete {path}: {exc}")

    def find_umu_run(self) -> str | None:
        """Return the path to umu-run, checking runner_dir first then PATH.

        Returns:
            Absolute path string if found, None otherwise.
        """
        user_runner = Paths.runner_dir() / "umu-run"
        if user_runner.is_file() and os.access(str(user_runner), os.X_OK):
            return str(user_runner)
        return shutil.which("umu-run")

    def scan_games(self) -> list[GameDict]:
        """Load all game JSON files from games_dir and populate self.games.

        Each game dict is enriched with ``install_dir`` (inferred from exe_path
        when missing) and ``game_file`` pointing to the source JSON path.
        Malformed files are logged and skipped.

        Returns:
            The refreshed list of game dicts.
        """
        self.games = []
        for game_file in sorted(self.games_dir.glob("*.json")):
            try:
                data = self._load_game_record(game_file)
                if not data.get('install_dir'):
                    exe_path = data.get('exe_path', '')
                    if exe_path and Path(exe_path).exists():
                        data['install_dir'] = find_game_root(exe_path) or str(Path(exe_path).resolve().parent)
                    else:
                        data['install_dir'] = str(game_file.parent)

                data['game_file'] = str(game_file)
                self.games.append(data)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.error(f"Error reading {game_file}: {exc}")
        event_bus.library_refreshed.emit()
        return self.games

    def get_games(self) -> list[GameDict]:
        """Return all games sorted alphabetically by name (case-insensitive)."""
        return sorted(self.games, key=lambda g: g['name'].lower())

    def get_game(self, name: str) -> GameDict | None:
        """Find and return a game by exact name match, or None if not found."""
        for game in self.games:
            if game['name'] == name:
                return game
        return None

    def add_game(
        self,
        name: str,
        exe: str,
        proton: str,
        args: str = "",
        custom_overrides: str = "",
        install_dir: str = "",
        env_vars: dict[str, str] | None = None,
        prefix_path: str = "",
        fingerprint_lock: bool = False,
        wrapper_command: str = "",
        exe_match_mode: str = "auto",
    ) -> bool:
        """Create a new game JSON config and rescan the game list.

        Args:
            name: Display name for the game.
            exe: Path to the game executable.
            proton: Proton version string (resolved via find_proton_path).
            args: Extra launch arguments.
            custom_overrides: DLL override string.
            install_dir: Game installation directory.
            env_vars: Additional environment variables.
            prefix_path: Custom Wine prefix path (empty for default).
            fingerprint_lock: Whether to enable bwrap fingerprint locking.
            wrapper_command: Optional wrapper command (e.g. mangohud).
            exe_match_mode: Executable match mode ("auto" or "exact").

        Returns:
            True on success, False if the proton version is not found or
            the file cannot be written.
        """
        proton_path = self.find_proton_path(proton) if proton else None
        if proton and not proton_path:
            logger.error(f"Proton version not found: {proton}")
            return False

        game_file = self.games_dir / f"{safe_name(name)}.json"
        data = {
            'name': name,
            'exe_path': exe,
            'proton_path': proton_path or '',
            'proton_version': proton,
            'launch_args': args,
            'custom_overrides': custom_overrides,
            'install_dir': install_dir,
            'env_vars': env_vars or {},
            'prefix_path': prefix_path,
            'fingerprint_lock': fingerprint_lock,
            'wrapper_command': wrapper_command,
            'exe_match_mode': exe_match_mode,
        }

        try:
            self._write_game_record(game_file, data)
            self.scan_games()
            event_bus.game_added.emit(name)
            return True
        except OSError as exc:
            logger.error(f"Failed to save game: {exc}")
            return False

    def update_custom_overrides(self, game: GameDict, new_overrides: str) -> bool:
        """Persist a new DLL override string for a game.

        Returns:
            True on success, False on I/O or parse error.
        """
        return self._update_game_record(Path(game['game_file']), {'custom_overrides': new_overrides})

    def update_install_dir(self, game_name: str, install_dir: str) -> bool:
        """Set or update the auto-detected install directory for a game.

        Skips the write when the stored value already matches *install_dir*.

        Returns:
            True if the record was updated, False if the game is not found,
            the value is unchanged, or the write fails.
        """
        game = self.get_game(game_name)
        if not game or game.get('install_dir') == install_dir:
            return False
        return self._update_game_record(Path(game['game_file']), {'install_dir': install_dir})

    def update_exe_path(self, game: GameDict, exe_path: str, *, exe_match_mode: str | None = None) -> bool:
        """Update the executable path and optionally the exe_match_mode for a game.

        Returns:
            True on success, False on I/O or parse error.
        """
        updates = {'exe_path': exe_path}
        if exe_match_mode is not None:
            updates['exe_match_mode'] = exe_match_mode
        return self._update_game_record(Path(game['game_file']), updates)

    def get_default_prefix_path(self, game_name: str) -> Path:
        """Return the default Wine prefix path for a game based on its safe_name."""
        return self.prefixes_dir / f"{safe_name(game_name)}prefix"

    def find_proton_path(self, proton_name: str) -> str | None:
        """Search ~/.steam/steam/compatibilitytools.d for a matching Proton directory.

        Args:
            proton_name: Substring to match against directory names.

        Returns:
            Absolute path string to the Proton directory, or None if not found.
        """
        steam_dir = Path.home() / ".steam/steam/compatibilitytools.d"
        if not steam_dir.exists():
            return None
        for proton_dir in steam_dir.glob("*"):
            if not proton_dir.is_dir():
                continue
            if proton_name in proton_dir.name and (proton_dir / "proton").exists():
                return str(proton_dir)
        return None

    def is_game_running(self, game_name: str) -> bool:
        """Return whether the given game is currently running."""
        return self.launcher.is_game_running(game_name)

    def stop_game(self, game_name: str) -> bool:
        """Stop a running game process. Returns True on success."""
        return self.launcher.stop_game(game_name)

    def launch_game(self, game_name: str) -> str:
        """Launch a game via the launcher. Returns a status/error message."""
        return self.launcher.launch_game(game_name)

    def on_game_exited(self, game_name: str) -> None:
        """Notify the launcher that a game process has exited."""
        self.launcher.on_game_exited(game_name)

    def launch_winetricks(self, prefix_path: str, proton_name: str | None = None) -> subprocess.Popen | None:
        """Launch winetricks for the given prefix, optionally using a specific Proton."""
        return self.launcher.launch_winetricks(prefix_path, proton_name)

    def create_game_shortcut(self, game: GameDict) -> tuple[bool, str]:
        """Create a .desktop shortcut for the game. Returns (success, message)."""
        return self.launcher.create_game_shortcut(game)

    def remove_game_shortcut(self, game_name: str) -> bool:
        """Remove the .desktop shortcut for the game. Returns True on success."""
        return self.launcher.remove_game_shortcut(game_name)

    def has_game_shortcut(self, game_name: str) -> bool:
        """Return whether a .desktop shortcut exists for the game."""
        return self.launcher.has_game_shortcut(game_name)
