"""Theme data model — leaf module with no intra-package dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceColors:
    window_bg: str
    nav_bg: str
    panel_bg: str
    content_bg: str


@dataclass(frozen=True)
class SelectionColors:
    nav_accent: str
    selection_bg: str
    hover_bg: str


@dataclass(frozen=True)
class StatusColors:
    warning: str
    error: str
    success: str
    info: str
    danger_hover: str
    text_disabled: str


@dataclass(frozen=True)
class Theme:
    name: str
    key: str
    accent: str
    accent_soft: str
    bg: str
    border: str
    text: str
    text_dim: str
    chrome_bg: str = ""
    status_warning: str = ""
    status_error: str = ""
    status_success: str = ""
    status_info: str = ""
    danger_hover: str = ""
    text_disabled: str = ""
