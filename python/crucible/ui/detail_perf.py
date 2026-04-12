"""Per-game performance, gamescope, scripts, and security section builders.

Each builder returns ``(widget, controls_dict)`` so the caller can wire
signals and read values for auto-save.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from crucible.core.types import GameDict
from crucible.ui.detail_forms import _ConfigRow, _ConfigSection
from crucible.ui.detail_widgets import _StateRow


# -- helpers ---------------------------------------------------------------


def _section_content() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    return w, lay


# -- builders --------------------------------------------------------------


def build_perf_section(game: GameDict) -> tuple[QWidget, dict]:
    """Gamemode + Gamescope enable toggles."""
    w, lay = _section_content()
    gm = _StateRow("gamemode")
    gm.setChecked(game.get("enable_gamemode", False))
    lay.addWidget(gm)

    gs = _StateRow("gamescope")
    gs.setChecked(game.get("enable_gamescope", False))
    lay.addWidget(gs)

    return w, {"gamemode": gm, "gamescope": gs}


def build_gamescope_section(game: GameDict) -> tuple[QWidget, dict]:
    """Full gamescope settings: resolution, upscale, FPS, window, cursor."""
    w, lay = _section_content()
    sec = _ConfigSection()
    gs = game.get("gamescope_settings", {})
    edits: dict[str, QLineEdit] = {}

    def _add(key: str, label: str, ctrl_name: str) -> None:
        row = _ConfigRow(key, label)
        row.setText(gs.get(key, ""))
        edits[ctrl_name] = row.edit
        sec.add_row(row)

    _add("game_width", "G.W", "game_w")
    _add("game_height", "G.H", "game_h")
    _add("upscale_width", "U.W", "up_w")
    _add("upscale_height", "U.H", "up_h")
    _add("upscale_method", "MTHD", "method")
    _add("window_type", "WNDW", "window")
    _add("fps_limiter", "FPS", "fps")
    _add("fps_limiter_no_focus", "FPS2", "fps_nofocus")
    lay.addWidget(sec)

    grab = _StateRow("force grab cursor")
    grab.setChecked(gs.get("enable_force_grab_cursor", False))
    lay.addWidget(grab)

    extra = _ConfigSection()
    row = _ConfigRow("additional_options", "XTRA")
    row.setText(gs.get("additional_options", ""))
    edits["additional"] = row.edit
    extra.add_row(row)
    lay.addWidget(extra)

    return w, {**edits, "grab_cursor": grab}


def build_scripts_section(game: GameDict, on_browse) -> tuple[QWidget, dict]:
    """Pre-launch and post-launch script paths."""
    w, lay = _section_content()
    sec = _ConfigSection()

    pre_row = _ConfigRow(
        "pre_launch_script", "PRE",
        on_browse=on_browse, browse_key="pre_launch_script",
    )
    pre_row.setText(game.get("pre_launch_script", ""))
    sec.add_row(pre_row)

    post_row = _ConfigRow(
        "post_launch_script", "POST",
        on_browse=on_browse, browse_key="post_launch_script",
    )
    post_row.setText(game.get("post_launch_script", ""))
    sec.add_row(post_row)

    lay.addWidget(sec)
    return w, {"pre_script": pre_row.edit, "post_script": post_row.edit}


def build_security_section(game: GameDict) -> tuple[QWidget, dict]:
    """Fingerprint lock toggle."""
    w, lay = _section_content()
    fp = _StateRow("fingerprint lock")
    fp.setChecked(game.get("fingerprint_lock", False))
    lay.addWidget(fp)
    return w, {"fingerprint": fp}
