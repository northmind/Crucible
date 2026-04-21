"""App-level preferences stored via QSettings.

These are non-game settings that control application behaviour —
appearance, window behaviour, update policy, paths, and logging.
Theme/animation settings remain in ``theme_system`` for backwards
compatibility; everything else lives here.
"""

from __future__ import annotations

from crucible.ui.theme_system import get_settings


# -- Behaviour -------------------------------------------------------------

def minimize_to_tray() -> bool:
    """Whether closing the window minimises to tray (default True)."""
    return get_settings().value("minimize_to_tray", True, type=bool)


def set_minimize_to_tray(enabled: bool) -> None:
    get_settings().setValue("minimize_to_tray", enabled)


def restore_geometry() -> bool:
    """Whether window size/position is persisted across sessions."""
    return get_settings().value("restore_geometry", True, type=bool)


def set_restore_geometry(enabled: bool) -> None:
    get_settings().setValue("restore_geometry", enabled)


def sidebar_collapsed() -> bool:
    """Whether the main navigation sidebar starts collapsed."""
    return get_settings().value("sidebar_collapsed", False, type=bool)


def set_sidebar_collapsed(collapsed: bool) -> None:
    get_settings().setValue("sidebar_collapsed", collapsed)


# -- Updates ---------------------------------------------------------------

def auto_update_umu() -> bool:
    """Whether umu-run is automatically updated on startup (default True)."""
    return get_settings().value("auto_update_umu", True, type=bool)


def set_auto_update_umu(enabled: bool) -> None:
    get_settings().setValue("auto_update_umu", enabled)


# -- Paths -----------------------------------------------------------------

def custom_proton_dir() -> str:
    """Extra directory to scan for Proton installations (empty = none)."""
    return get_settings().value("custom_proton_dir", "", type=str)


def set_custom_proton_dir(path: str) -> None:
    get_settings().setValue("custom_proton_dir", path)


# -- Debug -----------------------------------------------------------------

def log_level() -> str:
    """Console log level: ``"info"``, ``"debug"``, or ``"off"``."""
    return get_settings().value("log_level", "info", type=str)


def set_log_level(level: str) -> None:
    get_settings().setValue("log_level", level)


# -- Appearance ------------------------------------------------------------

def font_family() -> str:
    """UI font family (default: Fira Code)."""
    return get_settings().value("font_family", "Fira Code", type=str)


def set_font_family(family: str) -> None:
    get_settings().setValue("font_family", family)
