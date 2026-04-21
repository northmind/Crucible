from __future__ import annotations

"""Process lifecycle management: stop, reap, and screensaver inhibit."""

import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_REAP_DEADLINE_SECS = 5
_REAP_POLL_INTERVAL_SECS = 0.2
_DBUS_TIMEOUT_SECS = 5
_PIPE_READ_BUFSIZE = 32


def detached_fork(cmd: list[str], env: dict[str, str], cwd: str, log_file_path: Path) -> int:
    """Double-fork to detach a process from the caller's process tree.

    KDE groups windows by process tree.  ``Popen(start_new_session=True)``
    is insufficient — only a true double-fork reparents to PID 1.
    Returns the grandchild PID, or 0 on failure.
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
                        os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644,
                    )
                    os.dup2(log_fd, 1)
                    os.dup2(log_fd, 2)
                    os.close(log_fd)
                    os.chdir(cwd)
                    os.execvpe(cmd[0], cmd, env)
                except Exception as exc:
                    os.write(2, f"Failed to launch {cmd[0]}: {exc}\n".encode(errors='replace'))
                os._exit(1)
            else:
                os.write(w_fd, str(grandchild).encode())
                os.close(w_fd)
                os._exit(0)
        except Exception as exc:
            logger.debug(f"Detached fork failed for {cmd[0]}: {exc}")
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
        logger.debug(f"waitpid failed for child {child}: {exc}")
    try:
        return int(buf.strip())
    except ValueError as exc:
        logger.debug(f"Failed to parse pid from {buf!r}: {exc}")
        return 0


class ProcessControlMixin:
    """Game process stop/reap and screensaver inhibit for GameLauncher.

    Expects the concrete class to have: ``_running`` (dict mapping
    game_name -> entry dict with pid, uuid, ss_cookie) and
    ``_running_lock`` (threading.Lock guarding ``_running``).
    """

    def is_game_running(self, game_name: str) -> bool:
        """Return True if the game's top-level process or any descendant is still alive."""
        with self._running_lock:
            entry = self._running.get(game_name)
        if not entry:
            return False
        
        pid = entry.get('pid', 0)
        uuid_str = entry.get('uuid', '')

        if pid:
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                pass
            except PermissionError:
                return True
        
        if uuid_str:
            pids = self._scan_uuid_pids(uuid_str)
            if pids:
                return True

        return False

    def on_game_exited(self, game_name: str) -> None:
        """Clean up after a game exits: remove record, uninhibit screensaver."""
        with self._running_lock:
            entry = self._running.pop(game_name, None)
        ss_cookie = entry.get('ss_cookie') if entry else None
        if ss_cookie is not None:
            self._uninhibit_screensaver(ss_cookie)

    def stop_game(self, game_name: str) -> bool:
        """Send SIGTERM to all game processes and schedule reap."""
        with self._running_lock:
            entry = self._running.get(game_name)
            if entry is not None:
                entry['stopping'] = True
        if not entry:
            return False

        pid = entry.get('pid', 0)
        game_uuid = entry.get('uuid', '')

        pids = ([pid] + self._get_descendants(pid)) if pid else []
        if game_uuid:
            pids = list(set(pids) | self._scan_uuid_pids(game_uuid))

        for dpid in pids:
            try:
                os.kill(dpid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except PermissionError:
                logger.debug(f"Permission denied while stopping pid {dpid}")
            except OSError as exc:
                logger.debug(f"Failed to stop pid {dpid}: {exc}")

        ss_cookie = entry.get('ss_cookie')
        if ss_cookie is not None:
            self._uninhibit_screensaver(ss_cookie)

        def _reap() -> None:
            deadline = time.time() + _REAP_DEADLINE_SECS
            while time.time() < deadline:
                alive = []
                for dpid in pids:
                    try:
                        os.kill(dpid, 0)
                        alive.append(dpid)
                    except ProcessLookupError:
                        continue
                    except PermissionError:
                        alive.append(dpid)
                    except OSError as exc:
                        logger.debug(f"Failed to probe pid {dpid}: {exc}")
                if not alive:
                    if hasattr(self, 'on_game_exited'):
                        self.on_game_exited(game_name)
                    return
                time.sleep(_REAP_POLL_INTERVAL_SECS)
            for dpid in pids:
                try:
                    os.kill(dpid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            if hasattr(self, 'on_game_exited'):
                self.on_game_exited(game_name)

        threading.Thread(target=_reap, daemon=True).start()
        return True

    # ------------------------------------------------------------------
    # Process tree helpers
    # ------------------------------------------------------------------

    def _get_descendants(self, pid: int) -> list[int]:
        """Walk /proc to find all descendant PIDs of *pid*."""
        result = []
        stack = [pid]
        while stack:
            p = stack.pop()
            try:
                for tid in Path(f'/proc/{p}/task').iterdir():
                    try:
                        for child_str in (tid / 'children').read_text().split():
                            child = int(child_str)
                            result.append(child)
                            stack.append(child)
                    except (OSError, ValueError) as exc:
                        logger.debug(f"Failed to inspect children for task {tid}: {exc}")
            except OSError as exc:
                logger.debug(f"Failed to scan descendants for pid {p}: {exc}")
        return result

    def _scan_uuid_pids(self, game_uuid: str) -> set[int]:
        """Scan /proc for processes carrying our CRUCIBLE_GAME_ID.

        Reads each process's environ as raw bytes and searches for the
        target key=value without decoding the entire mapping, which is
        significantly faster than building a full dict per PID.
        """
        needle = f'CRUCIBLE_GAME_ID={game_uuid}'.encode()
        result = set()
        try:
            for p in Path('/proc').iterdir():
                if not p.name.isdigit():
                    continue
                try:
                    data = (p / 'environ').read_bytes()
                    if needle in data:
                        result.add(int(p.name))
                except (OSError, ValueError):
                    continue
        except OSError as exc:
            logger.debug(f"Failed to scan UUID pids for {game_uuid}: {exc}")
        return result

    # ------------------------------------------------------------------
    # Screensaver inhibit
    # ------------------------------------------------------------------

    def _inhibit_screensaver(self) -> int | None:
        """Inhibit the screensaver via D-Bus and return the cookie."""
        try:
            result = subprocess.run(
                [
                    'dbus-send', '--session',
                    '--dest=org.freedesktop.ScreenSaver',
                    '--type=method_call', '--print-reply',
                    '/org/freedesktop/ScreenSaver',
                    'org.freedesktop.ScreenSaver.Inhibit',
                    'string:Crucible', 'string:Game is running',
                ],
                capture_output=True, text=True, timeout=_DBUS_TIMEOUT_SECS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith('uint32'):
                        return int(line.split()[1])
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            logger.debug(f"Could not inhibit screensaver: {e}")
        return None

    def _uninhibit_screensaver(self, cookie: int) -> None:
        """Release a screensaver inhibit lock."""
        try:
            subprocess.run(
                [
                    'dbus-send', '--session',
                    '--dest=org.freedesktop.ScreenSaver',
                    '--type=method_call',
                    '/org/freedesktop/ScreenSaver',
                    'org.freedesktop.ScreenSaver.UnInhibit',
                    f'uint32:{cookie}',
                ],
                capture_output=True, timeout=_DBUS_TIMEOUT_SECS,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug(f"Could not uninhibit screensaver: {e}")
