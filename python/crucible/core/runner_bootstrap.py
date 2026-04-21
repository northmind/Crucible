from __future__ import annotations

import logging
import shutil
import stat
from pathlib import Path

from crucible.core.paths import Paths

logger = logging.getLogger(__name__)

_RUNNER_NAME = 'umu-run'
_VERSION_NAME = 'umu-run.version'


def _bundled_bootstrap_dir() -> Path:
    return Path(__file__).resolve().parents[2] / 'bootstrap'


def ensure_seeded_runner() -> None:
    dest_dir = Paths.runner_dir()
    dest = dest_dir / _RUNNER_NAME
    if dest.is_file() and dest.stat().st_size > 0:
        return

    bootstrap_dir = _bundled_bootstrap_dir()
    source = bootstrap_dir / _RUNNER_NAME
    if not source.is_file():
        return

    try:
        shutil.copy2(source, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        version_source = bootstrap_dir / _VERSION_NAME
        if version_source.is_file():
            shutil.copy2(version_source, dest_dir / _VERSION_NAME)

        logger.info(f"Seeded bundled umu-run into {dest}")
    except OSError as exc:
        logger.warning(f"Failed to seed bundled umu-run: {exc}")
