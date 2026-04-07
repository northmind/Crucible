"""Shared type definitions for the Crucible Launcher."""

from typing import TypedDict


class GameDict(TypedDict, total=False):
    """Schema for a game configuration dictionary.

    All persisted keys are written to ``~/.local/share/crucible-launcher/games/{safe_name}.json``
    by :meth:`crucible.core.managers.GameManager.add_game`.  The ``game_file`` key is
    injected at runtime by :meth:`~crucible.core.managers.GameManager.scan_games` and
    is never serialised to disk.
    """

    name: str
    exe_path: str
    proton_path: str
    proton_version: str
    launch_args: str
    custom_overrides: str
    install_dir: str
    env_vars: dict[str, str]
    prefix_path: str
    fingerprint_lock: bool
    wrapper_command: str
    exe_match_mode: str
    game_file: str  # runtime-only, not persisted
