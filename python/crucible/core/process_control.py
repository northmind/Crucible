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


class ProcessControlMixin:
    """Game process stop/reap and screensaver inhibit for GameLauncher.

    Expects the concrete class to have: ``_running`` (dict mapping
    game_name -> entry dict with pid, uuid, ss_cookie) and
    ``_running_lock`` (threading.Lock guarding ``_running``).
    """

    def is_game_running(self, game_name: str) -> bool:
        """Return True if the game's top-level process is still alive."""
        with self._running_lock:
            entry = self._running.get(game_name)
        if not entry:
            return False
        pid = entry.get('pid', 0)
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

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
            entry = self._running.pop(game_name, None)
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
                    return
                time.sleep(_REAP_POLL_INTERVAL_SECS)
            for dpid in pids:
                try:
                    os.kill(dpid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

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

    @staticmethod
    def _read_proc_environ(pid: int) -> dict[str, str]:
        """Read the environment variables of process *pid* from /proc."""
        try:
            data = Path(f'/proc/{pid}/environ').read_bytes()
            result = {}
            for entry in data.split(b'\x00'):
                if b'=' in entry:
                    k, _, v = entry.partition(b'=')
                    result[k.decode(errors='replace')] = v.decode(errors='replace')
            return result
        except OSError as exc:
            logger.debug(f"Failed to read environment for pid {pid}: {exc}")
            return {}

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
