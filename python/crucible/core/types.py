"""Shared type definitions for the Crucible Launcher."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict


class GamescopeSettings(TypedDict, total=False):
    """Structured gamescope configuration.

    Mirrors Heroic's ``GameScopeSettings`` interface.  Boolean flags use
    native ``bool``; remaining values are strings so they round-trip
    through JSON without type coercion.
    """

    enable_force_grab_cursor: bool
    window_type: str         # "fullscreen" | "borderless"
    game_width: str          # inner render width, e.g. "1280"
    game_height: str         # inner render height
    upscale_width: str       # gamescope output width
    upscale_height: str      # gamescope output height
    upscale_method: str      # "fsr" | "nis" | "integer" | "stretch"
    fps_limiter: str         # max FPS when focused
    fps_limiter_no_focus: str  # max FPS when unfocused
    additional_options: str  # raw CLI flags appended verbatim


class GameDict(TypedDict, total=False):
    """Schema for a game configuration dictionary.

    All persisted keys are written to ``~/.local/share/crucible-launcher/games/{safe_name}.json``
    by :meth:`crucible.core.managers.GameManager.add_game`.  The ``game_file`` key is
    injected at runtime by :meth:`~crucible.core.managers.GameManager.scan_games` and
    is never serialised to disk.

    Keys that also appear in :class:`crucible.core.global_config.GlobalConfig`
    support two-tier inheritance: a per-game value overrides the global default.
    """

    name: str
    exe_path: str
    proton_path: str
    proton_version: str
    launch_args: str
    custom_overrides: str
    install_dir: str
    env_vars: dict[str, str]
    disabled_env_vars: list[str]
    prefix_path: str
    fingerprint_lock: bool
    wrapper_command: str
    exe_match_mode: str

    enable_gamemode: bool
    enable_mangohud: bool
    enable_gamescope: bool
    disabled_global_flags: list[str]
    gamescope_settings: GamescopeSettings

    # Playtime tracking
    playtime_seconds: int       # cumulative play time in seconds
    last_played: str            # ISO 8601 timestamp of last session end

    game_file: str  # runtime-only, not persisted


@dataclass
class LaunchContext:
    """Carries state through the validate → prepare → execute pipeline."""

    game: dict                              # raw game dict from scan
    resolved: dict = field(default_factory=dict)  # after GlobalConfig merge
    exe_path: str = ""
    proton_path: str = ""
    umu: str = ""
    sname: str = ""
    prefix_path: Path = field(default_factory=Path)
    log_file_path: Path = field(default_factory=Path)
    env: dict[str, str] = field(default_factory=dict)
    game_uuid: str = ""
    game_cmd: list[str] = field(default_factory=list)
    cwd: str = ""
