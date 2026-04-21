from __future__ import annotations

"""Core game-launch logic using UMU/Proton with double-fork detach."""

import hashlib
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from crucible.core.paths import safe_name, clean_env, find_game_root, find_app_id_in_game_dir
from crucible.core.desktop_shortcuts import DesktopShortcutMixin
from crucible.core.events import event_bus
from crucible.core.game_state import GameState, GameStateTracker
from crucible.core.game_utils import _build_dll_overrides, _load_json_file, _write_json_file
from crucible.core.process_control import ProcessControlMixin, detached_fork
from crucible.core.types import GameDict, LaunchContext
from crucible.core.launch_env import (
    validate_launch_prereqs, resolve_prefix, validate_prefix,
    prepare_log_dir, build_env, build_command, resolve_proton_path,
)

if TYPE_CHECKING:
    from crucible.core.managers import GameManager

logger = logging.getLogger(__name__)


class GameLauncher(DesktopShortcutMixin, ProcessControlMixin):
    """Launches Windows games via UMU/Proton inside a Wine prefix."""

    def __init__(self, game_manager: GameManager) -> None:
        self._gm = game_manager
        self._running: dict[str, dict] = {}
        self._running_lock = threading.Lock()
        self.state = GameStateTracker()

        self.launcher_desktop_file = Path.home() / '.local/share/applications/crucible.desktop'

        self._ensure_launcher_desktop_file()
        self._cleanup_old_desktop_files()

    @staticmethod
    def _steam_id_for_name(game_name: str, raw_appid: str) -> str:
        """Derive a stable numeric Steam app ID from the game name."""
        if raw_appid != 'umu-default':
            return raw_appid
        return str(int(hashlib.md5(game_name.encode()).hexdigest()[:8], 16) % 900000 + 100000)

    @staticmethod
    def _timestamp_log_path(log_dir: Path) -> Path:
        """Generate a unique timestamped log file path."""
        _MAX_ATTEMPTS = 1000
        for _ in range(_MAX_ATTEMPTS):
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            candidate = log_dir / f"{stamp}.log"
            if not candidate.exists():
                return candidate
            time.sleep(0.001)
        raise RuntimeError(f"Could not create unique log path after {_MAX_ATTEMPTS} attempts")

    @staticmethod
    def _resolve_appid(game: GameDict) -> str:
        """Find a steam_appid.txt by locating the game root, then searching it."""
        exe_path = game.get('exe_path', '')
        if exe_path:
            game_root = find_game_root(exe_path) or str(Path(exe_path).parent)
            app_id = find_app_id_in_game_dir(game_root)
            if app_id:
                return app_id
        return 'umu-default'

    def launch_game(self, game_name: str) -> str:
        """Launch a game; returns an empty string on success or an error message.

        Pipeline: validate → prepare → execute.
        """
        ctx, error = self._validate_launch(game_name)
        if error:
            return error
        error = self._prepare_launch(ctx, game_name)
        if error:
            self.state.force_idle(game_name)
            return error
        result = self._execute_launch(ctx, game_name)
        if result:  # non-empty = error
            self.state.force_idle(game_name)
        return result

    def _validate_launch(self, game_name: str) -> tuple[LaunchContext | None, str]:
        """Phase 1: look up the game, check state, run pre-launch checks."""
        current = self.state.get(game_name)
        if current in (GameState.RUNNING, GameState.STOPPING) and not self.is_game_running(game_name):
            logger.info("Clearing stale state for exited game %s", game_name)
            self.on_game_exited(game_name)
            current = self.state.get(game_name)
        if current != GameState.IDLE:
            return None, f"Game '{game_name}' is already {current.value}."

        game = self._gm.get_game(game_name)
        if not game:
            return None, f"Game '{game_name}' not found."

        resolved = self._gm.global_config.resolve(game)

        error = validate_launch_prereqs(resolved, self._gm)
        if error:
            return None, error

        if not self.state.transition(game_name, GameState.LAUNCHING):
            return None, f"Game '{game_name}' state changed concurrently."

        return LaunchContext(game=game, resolved=resolved), ""

    def _prepare_launch(self, ctx: LaunchContext, game_name: str) -> str:
        """Phase 2: resolve config, build env/command, prepare prefix + logs."""
        if not ctx.resolved:
            ctx.resolved = self._gm.global_config.resolve(ctx.game)

        ctx.exe_path = ctx.resolved['exe_path']
        ctx.proton_path = resolve_proton_path(self._gm, ctx.resolved)
        ctx.umu = self._gm.find_umu_run()
        ctx.sname = safe_name(game_name)

        ctx.prefix_path = resolve_prefix(ctx.resolved, ctx.sname, self._gm.prefixes_dir)
        self._clean_broken_prefix_symlinks(ctx.prefix_path)

        prefix_error = validate_prefix(ctx.prefix_path)
        if prefix_error:
            return prefix_error

        ctx.log_file_path = prepare_log_dir(game_name, self._timestamp_log_path)

        ctx.env = build_env(
            ctx.resolved, game_name, ctx.sname, ctx.proton_path, ctx.prefix_path,
            self._resolve_appid, self._steam_id_for_name,
            _build_dll_overrides,
        )
        ctx.game_uuid = ctx.env['CRUCIBLE_GAME_ID']
        ctx.game_cmd = build_command(
            ctx.resolved, ctx.umu, ctx.exe_path, game_name, ctx.game_uuid, self._gm,
        )

        install_dir = ctx.resolved.get('install_dir', '').strip()
        ctx.cwd = (
            install_dir if install_dir and Path(install_dir).is_dir()
            else str(Path(ctx.exe_path).parent)
        )

        return ""

    def _execute_launch(self, ctx: LaunchContext, game_name: str) -> str:
        """Phase 3: fork the process, register it, inhibit screensaver."""
        try:
            pid = detached_fork(ctx.game_cmd, ctx.env, ctx.cwd, ctx.log_file_path)
            if not pid:
                return "Failed to launch game process."
            ss_cookie = self._inhibit_screensaver()
            with self._running_lock:
                self._running[game_name] = {
                    'pid': pid, 'uuid': ctx.game_uuid, 'ss_cookie': ss_cookie,
                    'started_at': time.monotonic(),
                }
            self.state.transition(game_name, GameState.RUNNING)
            event_bus.game_launched.emit(game_name)
            threading.Thread(
                target=self._watch_game_exit, args=(game_name, ctx.game_uuid), daemon=True,
            ).start()
            return ""
        except OSError as e:
            logger.error(f"Failed to launch {game_name}: {e}")
            return str(e)

    def stop_game(self, game_name: str) -> bool:
        """Transition to STOPPING, record playtime, then delegate to ProcessControlMixin."""
        with self._running_lock:
            started_at = (self._running.get(game_name) or {}).pop('started_at', None)
        self.state.transition(game_name, GameState.STOPPING)
        result = super().stop_game(game_name)

        if started_at is not None:
            elapsed = int(time.monotonic() - started_at)
            if elapsed > 0:
                self._record_playtime(game_name, elapsed)

        return result

    def on_game_exited(self, game_name: str) -> None:
        """Clean up process record, record playtime, and reset state."""
        with self._running_lock:
            entry = self._running.get(game_name)
            if entry and entry.get('cleanup_started'):
                return
            started_at = entry.pop('started_at', None) if entry else None
            if entry:
                entry['cleanup_started'] = True
            elif self.state.get(game_name) == GameState.IDLE:
                return
        self.state.force_idle(game_name)
        super().on_game_exited(game_name)

        if started_at is not None:
            elapsed = int(time.monotonic() - started_at)
            if elapsed > 0:
                self._record_playtime(game_name, elapsed)

        event_bus.game_exited.emit(game_name)

    def _watch_game_exit(self, game_name: str, game_uuid: str) -> None:
        """Watch a launched game and reconcile state after natural exit."""
        while True:
            with self._running_lock:
                entry = self._running.get(game_name)
                if not entry or entry.get('uuid') != game_uuid:
                    return
                if entry.get('stopping') or entry.get('cleanup_started'):
                    return
                pid = entry.get('pid', 0)
            if pid:
                try:
                    os.kill(pid, 0)
                    time.sleep(1.0)
                    continue
                except PermissionError:
                    time.sleep(1.0)
                    continue
                except ProcessLookupError:
                    pass
            if self._scan_uuid_pids(game_uuid):
                time.sleep(1.0)
                continue
            self.on_game_exited(game_name)
            return

    def _record_playtime(self, game_name: str, elapsed_seconds: int) -> None:
        """Persist cumulative playtime and last-played timestamp."""
        game = self._gm.get_game(game_name)
        if not game or not game.get('game_file'):
            return
        now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
        game_file = Path(game['game_file'])
        try:
            data = _load_json_file(game_file)
            prev = data.get('playtime_seconds', 0) or 0
            data['playtime_seconds'] = prev + elapsed_seconds
            data['last_played'] = now_iso
            _write_json_file(game_file, data)
            # Update in-memory game entry directly to avoid a full rescan
            game['playtime_seconds'] = data['playtime_seconds']
            game['last_played'] = now_iso
            logger.info(
                f"Recorded {elapsed_seconds}s playtime for {game_name} "
                f"(total: {prev + elapsed_seconds}s)"
            )
        except (OSError, ValueError) as exc:
            logger.error(f"Failed to record playtime for {game_name}: {exc}")

    def launch_winetricks(self, prefix_path: str, proton_name: str | None = None) -> subprocess.Popen | None:
        """Launch winetricks GUI in the given prefix."""
        umu = self._gm.find_umu_run()
        if not umu:
            logger.error("umu-run not found")
            return None

        proton_path = self._gm.find_proton_path(proton_name) if proton_name else None
        if not proton_path:
            logger.error(f"Proton not found: {proton_name}")
            return None

        Path(prefix_path).mkdir(parents=True, exist_ok=True)

        env = clean_env()
        env['WINEPREFIX'] = prefix_path
        env['PROTONPATH'] = proton_path
        env['GAMEID'] = '0'

        try:
            return subprocess.Popen(
                [umu, 'winetricks', '--gui'],
                env=env, stdin=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError as e:
            logger.error(f"Failed to launch winetricks: {e}")
            return None

    @staticmethod
    def _clean_broken_prefix_symlinks(prefix_path: Path) -> None:
        """Remove broken symlinks in system32/syswow64 directories."""
        dirs = [
            prefix_path / 'drive_c' / 'windows' / 'system32',
            prefix_path / 'drive_c' / 'windows' / 'syswow64',
        ]
        for d in dirs:
            if not d.is_dir():
                continue
            for entry in d.iterdir():
                if entry.is_symlink() and not entry.exists():
                    try:
                        entry.unlink()
                        logger.debug(f"Removed broken symlink: {entry}")
                    except OSError as e:
                        logger.debug(f"Could not remove broken symlink {entry}: {e}")
