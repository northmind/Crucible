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
from crucible.core.process_control import ProcessControlMixin
from crucible.core.types import GameDict
from crucible.core.launch_env import (
    validate_launch_prereqs, resolve_prefix, prepare_log_dir,
    build_env, build_command,
)

if TYPE_CHECKING:
    from crucible.core.managers import GameManager

logger = logging.getLogger(__name__)

_STEAM_APPID_WALK_DEPTH = 8
_PIPE_READ_BUFSIZE = 32


class GameLauncher(DesktopShortcutMixin, ProcessControlMixin):
    """Launches Windows games via UMU/Proton inside a Wine prefix."""

    def __init__(self, game_manager: GameManager) -> None:
        self._gm = game_manager
        self._running: dict[str, dict] = {}
        self._running_lock = threading.Lock()

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
        """Launch a game; returns an empty string on success or an error message."""
        game = self._gm.get_game(game_name)
        if not game:
            return f"Game '{game_name}' not found."

        error = validate_launch_prereqs(game, self._gm)
        if error:
            return error

        exe_path = game['exe_path']
        proton_version = game.get('proton_version', '')
        proton_path = (
            (self._gm.find_proton_path(proton_version) if proton_version else '')
            or game.get('proton_path', '')
        )
        umu = self._gm.find_umu_run()
        sname = safe_name(game_name)

        prefix_path = resolve_prefix(game, sname, self._gm.prefixes_dir)
        self._clean_broken_prefix_symlinks(prefix_path)
        log_file_path = prepare_log_dir(game_name, self._timestamp_log_path)

        env = build_env(
            game, game_name, sname, proton_path, prefix_path,
            self._resolve_appid, self._steam_id_for_name,
            self._gm._build_dll_overrides,
        )
        game_uuid = env['CRUCIBLE_GAME_ID']
        game_cmd = build_command(game, umu, exe_path, game_name, game_uuid, self._gm)

        install_dir = game.get('install_dir', '').strip()
        cwd = install_dir if install_dir and Path(install_dir).is_dir() else str(Path(exe_path).parent)

        try:
            pid = self._launch_detached(game_cmd, env, cwd, log_file_path)
            if not pid:
                return "Failed to launch game process."
            ss_cookie = self._inhibit_screensaver()
            with self._running_lock:
                self._running[game_name] = {
                    'pid': pid, 'uuid': game_uuid, 'ss_cookie': ss_cookie,
                }
            return ""
        except OSError as e:
            logger.error(f"Failed to launch {game_name}: {e}")
            return str(e)

    # ------------------------------------------------------------------
    # Double-fork detached launch
    # ------------------------------------------------------------------

    def _launch_detached(self, cmd: list[str], env: dict[str, str], cwd: str, log_file_path: Path) -> int:
        """Double-fork to fully detach the game process from Crucible's tree.

        This is intentional — KDE groups windows by process tree, and
        ``subprocess.Popen(start_new_session=True)`` does NOT achieve the
        same taskbar separation.  The double-fork reparents the game
        to PID 1.
        """
        r_fd, w_fd = os.pipe()
        child = os.fork()
        if child == 0:
            try:
                os.close(r_fd)
                os.setsid()
                grandchild = os.fork()
                if grandchild == 0:
                    try:
                        os.close(w_fd)
                        devnull = os.open('/dev/null', os.O_RDONLY)
                        os.dup2(devnull, 0)
                        os.close(devnull)
                        log_fd = os.open(
                            str(log_file_path),
                            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                            0o644,
                        )
                        os.dup2(log_fd, 1)
                        os.dup2(log_fd, 2)
                        os.close(log_fd)
                        os.chdir(cwd)
                        os.execvpe(cmd[0], cmd, env)
                    except Exception as exc:
                        os.write(2, f"Failed to launch process {cmd[0]}: {exc}\n".encode(errors='replace'))
                    os._exit(1)
                else:
                    os.write(w_fd, str(grandchild).encode())
                    os.close(w_fd)
                    os._exit(0)
            except Exception as exc:
                logger.debug(f"Detached launch pre-fork failed for {cmd[0]}: {exc}")
                try:
                    os.write(w_fd, b'0')
                    os.close(w_fd)
                except OSError:
                    pass
                os._exit(1)
        os.close(w_fd)
        buf = b''
        while True:
            try:
                chunk = os.read(r_fd, _PIPE_READ_BUFSIZE)
                if not chunk:
                    break
                buf += chunk
            except OSError:
                break
        os.close(r_fd)
        try:
            os.waitpid(child, 0)
        except OSError as exc:
            logger.debug(f"waitpid failed for detached launcher child {child}: {exc}")
        try:
            return int(buf.strip())
        except ValueError as exc:
            logger.debug(f"Failed to parse detached launcher pid from {buf!r}: {exc}")
            return 0

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
