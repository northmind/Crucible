"""Global Settings — General page builder.

Builds all sections for the Settings > General tab: Runner, Launch,
Environment, Scripts, Performance, Gamescope, and Security.  Returns a
controls dataclass so the caller can wire debounced saves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from crucible.core.global_config import GlobalConfig
from crucible.ui import styles
from crucible.ui.detail_forms import _ConfigRow, _ConfigSection
from crucible.ui.detail_widgets import _ProtonRow, _StateRow
from crucible.ui.panel_helpers import build_collapsible_section
from crucible.ui.tokens import SPACE_MD, SPACE_XL
from crucible.ui.widgets import make_scroll_page


# -- Controls bag ----------------------------------------------------------

@dataclass
class GeneralControls:
    """Holds references to every editable widget on the General page."""

    proton_group: QButtonGroup | None = None
    launch_args: QLineEdit | None = None
    dlls: QLineEdit | None = None
    wrapper: QLineEdit | None = None
    env: QLineEdit | None = None
    pre_script: QLineEdit | None = None
    post_script: QLineEdit | None = None
    gamemode: _StateRow | None = None
    gamescope: _StateRow | None = None
    gs_game_w: QLineEdit | None = None
    gs_game_h: QLineEdit | None = None
    gs_up_w: QLineEdit | None = None
    gs_up_h: QLineEdit | None = None
    gs_method: QLineEdit | None = None
    gs_window: QLineEdit | None = None
    gs_fps: QLineEdit | None = None
    gs_fps_nofocus: QLineEdit | None = None
    gs_grab_cursor: _StateRow | None = None
    gs_additional: QLineEdit | None = None
    fingerprint: _StateRow | None = None
    section_headers: dict[str, Any] = field(default_factory=dict)

    def all_edits(self) -> list[QLineEdit]:
        """Return every QLineEdit control for batch signal wiring."""
        return [
            e for e in (
                self.launch_args, self.dlls, self.wrapper, self.env,
                self.pre_script, self.post_script,
                self.gs_game_w, self.gs_game_h, self.gs_up_w, self.gs_up_h,
                self.gs_method, self.gs_window, self.gs_fps,
                self.gs_fps_nofocus, self.gs_additional,
            )
            if e is not None
        ]

    def all_toggles(self) -> list[_StateRow]:
        """Return every _StateRow toggle for batch signal wiring."""
        return [
            t for t in (
                self.gamemode, self.gamescope, self.gs_grab_cursor,
                self.fingerprint,
            )
            if t is not None
        ]


# -- Section builders ------------------------------------------------------


def _section_content() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    return w, lay


def _build_runner(
    cfg: GlobalConfig,
    parent: QWidget,
    proton_mgr: object,
    ctrl: GeneralControls,
) -> QWidget:
    w, lay = _section_content()
    group = QButtonGroup(parent)
    group.setExclusive(True)
    versions = proton_mgr.get_installed_names()
    current = cfg.get("proton_version", "")
    if versions:
        for v in versions:
            row = _ProtonRow(v)
            group.addButton(row)
            row.setChecked(v == current)
            lay.addWidget(row)
    else:
        lbl = QLabel("no proton installed")
        lbl.setContentsMargins(8, 2, 8, 2)
        lbl.setStyleSheet(styles.mono_label())
        lay.addWidget(lbl)
    ctrl.proton_group = group
    return w


def _build_launch(cfg: GlobalConfig, on_browse, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    sec = _ConfigSection()

    def _add(key: str, label: str, attr: str) -> None:
        row = _ConfigRow(key, label, on_browse=on_browse)
        row.setText(cfg.get(key, ""))
        setattr(ctrl, attr, row.edit)
        sec.add_row(row)

    _add("launch_args", "ARGS", "launch_args")
    _add("custom_overrides", "DLLS", "dlls")
    _add("wrapper_command", "WRAP", "wrapper")
    lay.addWidget(sec)
    return w


def _build_env(cfg: GlobalConfig, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    sec = _ConfigSection()
    row = _ConfigRow("env_vars", "ENV")
    env_dict = cfg.get("env_vars", {})
    text = " ".join(f"{k}={v}" for k, v in env_dict.items()) if env_dict else ""
    row.setText(text)
    ctrl.env = row.edit
    sec.add_row(row)
    lay.addWidget(sec)
    return w


def _build_scripts(cfg: GlobalConfig, on_browse, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    sec = _ConfigSection()

    def _add(key: str, label: str, attr: str) -> None:
        row = _ConfigRow(key, label, on_browse=on_browse, browse_key=key)
        row.setText(cfg.get(key, ""))
        setattr(ctrl, attr, row.edit)
        sec.add_row(row)

    _add("pre_launch_script", "PRE", "pre_script")
    _add("post_launch_script", "POST", "post_script")
    lay.addWidget(sec)
    return w


def _build_perf(cfg: GlobalConfig, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    gm = _StateRow("gamemode")
    gm.setChecked(cfg.get("enable_gamemode", False))
    ctrl.gamemode = gm
    lay.addWidget(gm)

    gs = _StateRow("gamescope")
    gs.setChecked(cfg.get("enable_gamescope", False))
    ctrl.gamescope = gs
    lay.addWidget(gs)
    return w


def _build_gamescope(cfg: GlobalConfig, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    sec = _ConfigSection()
    gs = cfg.get("gamescope_settings", {})

    def _add(key: str, label: str, attr: str) -> None:
        row = _ConfigRow(key, label)
        row.setText(gs.get(key, ""))
        setattr(ctrl, attr, row.edit)
        sec.add_row(row)

    _add("game_width", "G.W", "gs_game_w")
    _add("game_height", "G.H", "gs_game_h")
    _add("upscale_width", "U.W", "gs_up_w")
    _add("upscale_height", "U.H", "gs_up_h")
    _add("upscale_method", "MTHD", "gs_method")
    _add("window_type", "WNDW", "gs_window")
    _add("fps_limiter", "FPS", "gs_fps")
    _add("fps_limiter_no_focus", "FPS2", "gs_fps_nofocus")
    lay.addWidget(sec)

    grab = _StateRow("force grab cursor")
    grab.setChecked(gs.get("enable_force_grab_cursor", False))
    ctrl.gs_grab_cursor = grab
    lay.addWidget(grab)

    extra = _ConfigSection()
    row = _ConfigRow("additional_options", "XTRA")
    row.setText(gs.get("additional_options", ""))
    ctrl.gs_additional = row.edit
    extra.add_row(row)
    lay.addWidget(extra)
    return w


def _build_security(cfg: GlobalConfig, ctrl: GeneralControls) -> QWidget:
    w, lay = _section_content()
    fp = _StateRow("fingerprint lock")
    fp.setChecked(cfg.get("fingerprint_lock", False))
    ctrl.fingerprint = fp
    lay.addWidget(fp)
    return w


# -- Public API ------------------------------------------------------------

_SECTIONS: tuple[tuple[str, bool], ...] = (
    ("runner", True),
    ("launch", False),
    ("environment", False),
    ("scripts", False),
    ("performance", False),
    ("gamescope", False),
    ("security", False),
)

_BUILDERS = {
    "runner": lambda cfg, ctrl, **kw: _build_runner(cfg, kw["parent"], kw["proton_mgr"], ctrl),
    "launch": lambda cfg, ctrl, **kw: _build_launch(cfg, kw.get("on_browse"), ctrl),
    "environment": lambda cfg, ctrl, **kw: _build_env(cfg, ctrl),
    "scripts": lambda cfg, ctrl, **kw: _build_scripts(cfg, kw.get("on_browse"), ctrl),
    "performance": lambda cfg, ctrl, **kw: _build_perf(cfg, ctrl),
    "gamescope": lambda cfg, ctrl, **kw: _build_gamescope(cfg, ctrl),
    "security": lambda cfg, ctrl, **kw: _build_security(cfg, ctrl),
}


def build_general_page(
    *,
    global_config: GlobalConfig,
    proton_manager: object,
    parent: QWidget,
    on_browse=None,
) -> tuple[QWidget, GeneralControls]:
    """Build the full General settings page.

    Returns:
        (scroll_area, controls) -- the page widget and a dataclass of
        all editable controls for the caller to wire saves to.
    """
    scroll = make_scroll_page(
        margins=(SPACE_XL, 20, SPACE_XL, 20),
        spacing=SPACE_MD,
    )
    layout = scroll.widget().layout()
    ctrl = GeneralControls()

    kw = {"parent": parent, "proton_mgr": proton_manager, "on_browse": on_browse}
    for name, expanded in _SECTIONS:
        content = _BUILDERS[name](global_config, ctrl, **kw)
        section, header = build_collapsible_section(name, content, expanded=expanded)
        ctrl.section_headers[name] = header
        layout.addWidget(section)

    layout.addStretch()
    return scroll, ctrl
