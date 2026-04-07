"""Mixin providing game lifecycle operations (remove, delete, reset, rename)."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from crucible.core.paths import (
    Paths,
    artwork_safe_name,
    find_app_id_in_game_dir,
    find_game_root,
    safe_name,
)
from crucible.core.types import GameDict

if TYPE_CHECKING:
    from crucible.core.managers import GameManager

logger = logging.getLogger(__name__)


class GameLifecycleMixin:
    """Mixin for GameManager providing remove/delete/reset/rename operations."""

    def remove_game(self: GameManager, name: str, remove_prefix: bool = False) -> bool:
        """Delete a game's JSON config and optionally its Wine prefix.

        Args:
            name: Exact game name.
            remove_prefix: If True, also delete the game's Wine prefix directory.

        Returns:
            True on success, False if the game is not found or deletion fails.
        """
        game = self.get_game(name)
        if not game:
            return False
        game_file = Path(game['game_file'])
        try:
            if game_file.exists():
                game_file.unlink()
            if remove_prefix:
                sname = safe_name(name)
                stored = (game.get('prefix_path') or '').strip()
                prefix_path = Path(stored) if stored else self.prefixes_dir / f"{sname}prefix"
                if prefix_path.exists():
                    shutil.rmtree(prefix_path)
            self.scan_games()
            return True
        except OSError as exc:
            logger.error(f"Failed to remove {name}: {exc}")
            return False

    def delete_game(self: GameManager, name: str) -> bool:
        """Remove a game and all associated data.

        Deletes the game JSON, Wine prefix, cached artwork, log files,
        fingerprint data, and desktop shortcut.

        Args:
            name: Exact game name.

        Returns:
            True on success, False if the game is not found or any step fails.
        """
        game = self.get_game(name)
        if not game:
            return False
        try:
            if not self.remove_game(name, remove_prefix=True):
                return False

            sname = safe_name(name)
            artwork_dir = Paths.artwork_dir()
            artwork_safe = artwork_safe_name(name)
            candidates: list[Path] = [artwork_dir / f"{artwork_safe}.jpg"]

            exe_path = game.get('exe_path', '')
            if exe_path:
                exe_digest = hashlib.sha1(
                    exe_path.strip().lower().encode('utf-8'),
                ).hexdigest()[:16]
                candidates.append(artwork_dir / f"exe_{exe_digest}.jpg")
                game_root = find_game_root(exe_path)
                if game_root:
                    app_id = find_app_id_in_game_dir(game_root)
                    if app_id:
                        candidates.append(artwork_dir / f"app_{app_id}.jpg")

            candidates.append(Paths.artwork_dir() / 'icons' / f'{sname}.png')
            self._delete_paths(candidates)

            game_log_dir = Paths.game_logs_dir(name)
            for log_file in game_log_dir.glob("*.log"):
                log_file.unlink(missing_ok=True)

            self.fingerprint.clear(name)
            self.launcher.remove_game_shortcut(name)
            return True
        except OSError as exc:
            logger.error(f"Failed to delete game {name}: {exc}")
            return False

    def reset_game_prefix(self: GameManager, name: str) -> bool:
        """Delete the Wine prefix directory for a game.

        Args:
            name: Exact game name.

        Returns:
            True on success (including when the prefix doesn't exist),
            False if the game is not found or deletion fails.
        """
        game = self.get_game(name)
        if not game:
            return False
        sname = safe_name(name)
        stored = (game.get('prefix_path') or '').strip()
        prefix_path = Path(stored) if stored else self.prefixes_dir / f"{sname}prefix"
        try:
            if prefix_path.exists():
                shutil.rmtree(prefix_path)
            return True
        except OSError as exc:
            logger.error(f"Failed to reset prefix for {name}: {exc}")
            return False

    def clear_game_logs(self: GameManager, name: str) -> bool:
        """Remove all .log files in the game's log directory.

        Args:
            name: Exact game name.

        Returns:
            True on success, False if deletion fails.
        """
        try:
            game_log_dir = Paths.game_logs_dir(name)
            for log_file in game_log_dir.glob("*.log"):
                log_file.unlink(missing_ok=True)
            return True
        except OSError as exc:
            logger.error(f"Failed to clear logs for {name}: {exc}")
            return False

    def rename_game(self: GameManager, old_name: str, new_name: str) -> bool:
        """Rename a game by rewriting its JSON config under a new filename.

        The old JSON file is deleted if the new filename differs. Returns
        True immediately if old_name equals new_name.

        Args:
            old_name: Current game name.
            new_name: Desired new name.

        Returns:
            True on success, False if the game is not found or the rename fails.
        """
        if old_name == new_name:
            return True
        game = self.get_game(old_name)
        if not game:
            return False

        game_file = Path(game['game_file'])
        try:
            data = self._load_game_record(game_file)
            data['name'] = new_name
            new_game_file = self.games_dir / f"{safe_name(new_name)}.json"
            self._write_game_record(new_game_file, data)
            if game_file.resolve() != new_game_file.resolve():
                game_file.unlink()
            self.scan_games()
            return True
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error(f"Failed to rename {old_name} to {new_name}: {exc}")
            return False
