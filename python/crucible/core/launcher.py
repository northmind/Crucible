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

from crucible.core.paths import Paths, safe_name, clean_env
from crucible.core.desktop_shortcuts import DesktopShortcutMixin
from crucible.core.events import event_bus
from crucible.core.game_state import GameState, GameStateTracker
from crucible.core.process_control import ProcessControlMixin, detached_fork
from crucible.core.types import GameDict, LaunchContext
from crucible.core.launch_env import (
    validate_launch_prereqs, resolve_prefix, validate_prefix,
    prepare_log_dir, build_env, build_command, run_launch_script,
)

if TYPE_CHECKING:
    from crucible.core.managers import GameManager

logger = logging.getLogger(__name__)

_STEAM_APPID_WALK_DEPTH = 8


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
        """Walk parent directories to find a steam_appid.txt."""
        exe_path = game.get('exe_path', '')
        if exe_path:
            try:
                search = Path(exe_path).parent
                for _ in range(_STEAM_APPID_WALK_DEPTH):
                    candidate = search / 'steam_appid.txt'
                    if candidate.exists():
                        val = candidate.read_text().strip()
                        if val.isdigit():
                            return val
                        break
                    if search.name.lower() in ('binaries', 'win64', 'win32', 'windows', 'engine'):
                        search = search.parent
                    else:
                        break
            except OSError as exc:
                logger.debug(f"Failed to resolve Steam app id for {exe_path}: {exc}")
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

    # ------------------------------------------------------------------
    # Pipeline phases
    # ------------------------------------------------------------------

    def _validate_launch(self, game_name: str) -> tuple[LaunchContext | None, str]:
        """Phase 1: look up the game, check state, run pre-launch checks."""
        current = self.state.get(game_name)
        if current != GameState.IDLE:
            return None, f"Game '{game_name}' is already {current.value}."

        game = self._gm.get_game(game_name)
        if not game:
            return None, f"Game '{game_name}' not found."

        error = validate_launch_prereqs(game, self._gm)
        if error:
            return None, error

        if not self.state.transition(game_name, GameState.LAUNCHING):
            return None, f"Game '{game_name}' state changed concurrently."

        event_bus.game_state_changed.emit(game_name, GameState.LAUNCHING.value)
        return LaunchContext(game=game), ""

    def _prepare_launch(self, ctx: LaunchContext, game_name: str) -> str:
        """Phase 2: resolve config, build env/command, prepare prefix + logs."""
        ctx.resolved = self._gm.global_config.resolve(ctx.game)

        ctx.exe_path = ctx.resolved['exe_path']
        proton_version = ctx.resolved.get('proton_version', '')
        ctx.proton_path = (
            (self._gm.find_proton_path(proton_version) if proton_version else '')
            or ctx.resolved.get('proton_path', '')
        )
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
            self._gm._build_dll_overrides,
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

        pre_script = ctx.resolved.get('pre_launch_script', '')
        if pre_script:
            error = run_launch_script(pre_script, label="Pre-launch script")
            if error:
                return error

        return ""

    def _execute_launch(self, ctx: LaunchContext, game_name: str) -> str:
        """Phase 3: fork the process, register it, inhibit screensaver."""
        try:
            pid = self._launch_detached(ctx.game_cmd, ctx.env, ctx.cwd, ctx.log_file_path)
            if not pid:
                return "Failed to launch game process."
            ss_cookie = self._inhibit_screensaver()
            with self._running_lock:
                self._running[game_name] = {
                    'pid': pid, 'uuid': ctx.game_uuid, 'ss_cookie': ss_cookie,
                    'post_launch_script': ctx.resolved.get('post_launch_script', ''),
                }
            self.state.transition(game_name, GameState.RUNNING)
            event_bus.game_launched.emit(game_name)
            event_bus.game_state_changed.emit(game_name, GameState.RUNNING.value)
            return ""
        except OSError as e:
            logger.error(f"Failed to launch {game_name}: {e}")
            return str(e)

    # ------------------------------------------------------------------
    # State-aware overrides of ProcessControlMixin
    # ------------------------------------------------------------------

    def stop_game(self, game_name: str) -> bool:
        """Transition to STOPPING, then delegate to ProcessControlMixin."""
        self.state.transition(game_name, GameState.STOPPING)
        event_bus.game_state_changed.emit(game_name, GameState.STOPPING.value)
        result = super().stop_game(game_name)
        self.state.force_idle(game_name)
        event_bus.game_state_changed.emit(game_name, GameState.IDLE.value)
        return result

    def on_game_exited(self, game_name: str) -> None:
        """Clean up process record, run post-launch script, reset state."""
        with self._running_lock:
            entry = self._running.get(game_name)
        post_script = entry.get('post_launch_script', '') if entry else ''
        super().on_game_exited(game_name)
        self.state.force_idle(game_name)
        event_bus.game_exited.emit(game_name)
        event_bus.game_state_changed.emit(game_name, GameState.IDLE.value)
        if post_script:
            error = run_launch_script(post_script, label="Post-launch script")
            if error:
                logger.warning("Post-launch script failed for %s: %s", game_name, error)

    # ------------------------------------------------------------------
    # Double-fork detached launch
    # ------------------------------------------------------------------

    @staticmethod
    def _launch_detached(cmd: list[str], env: dict[str, str], cwd: str, log_file_path: Path) -> int:
        """Double-fork to fully detach the game process from Crucible's tree."""
        return detached_fork(cmd, env, cwd, log_file_path)

    # ------------------------------------------------------------------
    # Winetricks
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Prefix cleanup
    # ------------------------------------------------------------------

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
