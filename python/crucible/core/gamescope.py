"""Gamescope micro-compositor detection and command-line assembly."""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess

from crucible.core.types import GamescopeSettings

logger = logging.getLogger(__name__)


def _detect_gamescope_version(gamescope_bin: str) -> bool:
    """Return True if gamescope is "new" style (>= 3.12, has -F/--filter flag)."""
    try:
        result = subprocess.run(
            [gamescope_bin, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        help_text = (result.stdout or "") + (result.stderr or "")
        return "-F, --filter" in help_text
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_gamescope_command(settings: GamescopeSettings) -> list[str]:
    """Convert structured gamescope settings into a CLI prefix list.

    Returns an empty list if gamescope is disabled or not installed.
    The returned list ends with ``--`` so the caller can append the game
    command directly.

    Flag mapping matches Heroic Games Launcher (v2.x):
      -w/-h   game render resolution
      -W/-H   gamescope output resolution
      -F fsr/-U   upscale method (new/old)
      -f/-b       window type
      -r/-o       FPS limiter
      --force-grab-cursor
    """
    has_upscale = any(
        settings.get(key)
        for key in ("game_width", "game_height", "upscale_width", "upscale_height", "upscale_method", "window_type")
    )
    has_limiter = any(
        settings.get(key)
        for key in ("fps_limiter", "fps_limiter_no_focus")
    )
    has_misc = bool(settings.get("enable_force_grab_cursor", False))
    if not has_misc:
        has_misc = bool((settings.get("additional_options", "") or "").strip())
    if not has_upscale and not has_limiter and not has_misc:
        return []

    gamescope_bin = shutil.which("gamescope")
    if not gamescope_bin:
        logger.warning("Gamescope enabled but 'gamescope' not found on PATH.")
        return []

    new_version = _detect_gamescope_version(gamescope_bin)
    cmd: list[str] = [gamescope_bin]

    if has_upscale:
        gw = settings.get("game_width", "")
        gh = settings.get("game_height", "")
        uw = settings.get("upscale_width", "")
        uh = settings.get("upscale_height", "")
        if gw:
            cmd += ["-w", gw]
        if gh:
            cmd += ["-h", gh]
        if uw:
            cmd += ["-W", uw]
        if uh:
            cmd += ["-H", uh]

        method = settings.get("upscale_method", "").lower()
        if method == "fsr":
            cmd += ["-F", "fsr"] if new_version else ["-U"]
        elif method == "nis":
            cmd += ["-F", "nis"] if new_version else ["-Y"]
        elif method == "integer":
            cmd += ["-S", "integer"] if new_version else ["-i"]
        elif method == "stretch" and new_version:
            cmd += ["-S", "stretch"]

        wt = settings.get("window_type", "").lower()
        if wt == "fullscreen":
            cmd.append("-f")
        elif wt == "borderless":
            cmd.append("-b")

    if has_limiter:
        fps = settings.get("fps_limiter", "")
        fps_nf = settings.get("fps_limiter_no_focus", "")
        if fps:
            cmd += ["-r", fps]
        if fps_nf:
            cmd += ["-o", fps_nf]

    if settings.get("enable_force_grab_cursor", False):
        cmd.append("--force-grab-cursor")

    extra = settings.get("additional_options", "").strip()
    if extra:
        try:
            cmd += shlex.split(extra)
        except ValueError as exc:
            logger.warning("Could not parse gamescope additional_options: %s", exc)

    cmd.append("--")
    return cmd
