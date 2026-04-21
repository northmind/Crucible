from __future__ import annotations

import shutil
import logging
from pathlib import Path

from crucible.core.paths import safe_name as _safe

logger = logging.getLogger(__name__)


class FingerprintManager:
    def __init__(self, fingerprints_dir: Path) -> None:
        self.fingerprints_dir = fingerprints_dir
        fingerprints_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, game_name: str) -> bool:
        """Capture /proc/cpuinfo and /proc/version into the game's snapshot dir.

        Args:
            game_name: Display name of the game (sanitised via ``safe_name``).

        Returns:
            True on success, False if reading /proc files fails.
        """
        snap_dir = self.fingerprints_dir / _safe(game_name)
        snap_dir.mkdir(parents=True, exist_ok=True)
        try:
            (snap_dir / 'cpuinfo').write_bytes(Path('/proc/cpuinfo').read_bytes())
            (snap_dir / 'version').write_bytes(Path('/proc/version').read_bytes())
            return True
        except OSError as e:
            logger.error(f"Failed to snapshot fingerprint for {game_name}: {e}")
            return False

    def clear(self, game_name: str) -> None:
        """Remove the snapshot directory for a game, silently ignoring errors."""
        shutil.rmtree(self.fingerprints_dir / _safe(game_name), ignore_errors=True)

    def get_bwrap_args(self, game_name: str) -> list[str]:
        """Build bubblewrap CLI args that bind-mount the fingerprint snapshot over /proc.

        If ``bwrap`` is not installed, logs a warning and returns an empty list.
        If no snapshot exists yet, one is taken automatically before building
        the argument list.

        Args:
            game_name: Display name of the game (sanitised via ``safe_name``).

        Returns:
            A list of strings suitable for prefixing a subprocess command, or
            an empty list when bwrap is unavailable.
        """
        bwrap = shutil.which('bwrap')
        if not bwrap:
            logger.warning("fingerprint_lock enabled but bwrap not found — launching without isolation")
            return []

        snap_dir = self.fingerprints_dir / _safe(game_name)
        if not (snap_dir / 'cpuinfo').exists():
            self.snapshot(game_name)

        args = [
            bwrap,
            '--ro-bind', '/', '/',
            '--dev-bind', '/dev', '/dev',
            '--proc', '/proc',
            '--bind', '/tmp', '/tmp',
            '--bind', '/run', '/run',
            '--bind', str(Path.home()), str(Path.home()),
        ]
        if (snap_dir / 'cpuinfo').exists():
            args += ['--ro-bind', str(snap_dir / 'cpuinfo'), '/proc/cpuinfo']
        if (snap_dir / 'version').exists():
            args += ['--ro-bind', str(snap_dir / 'version'), '/proc/version']
        args.append('--')
        return args
