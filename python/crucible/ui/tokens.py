"""Design tokens — spacing, typography, layout, and animation constants."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve

# ---------------------------------------------------------------------------
# Spacing scale (px)
# ---------------------------------------------------------------------------
# Named after T-shirt sizes.  Values follow a near-doubling progression.

SPACE_NONE: int = 0
SPACE_2XS: int = 2
SPACE_XS: int = 4
SPACE_SM: int = 6
SPACE_MD: int = 8
SPACE_LG: int = 12
SPACE_XL: int = 16
SPACE_2XL: int = 24
SPACE_3XL: int = 32

# ---------------------------------------------------------------------------
# Typography scale (pt)
# ---------------------------------------------------------------------------
# Modular scale ~1.2 ratio, anchored at FONT_BASE = 9pt.

FONT_2XS: int = 7
FONT_XS: int = 8
FONT_BASE: int = 9
FONT_MD: int = 10
FONT_LG: int = 12
FONT_XL: int = 14

FONT_MONO: str = "'Courier New', monospace"

# ---------------------------------------------------------------------------
# Layout constants (px)
# ---------------------------------------------------------------------------

ROW_HEIGHT: int = 38
PANEL_WIDTH: int = 288
SIDEBAR_WIDTH: int = 44
TITLEBAR_HEIGHT: int = 36
NAV_BTN_SIZE: int = 32
ICON_BTN_SIZE: int = 18
SCROLLBAR_WIDTH: int = 2
PROGRESS_HEIGHT: int = 4

# ---------------------------------------------------------------------------
# Animation constants
# ---------------------------------------------------------------------------

ANIM_DURATION_MS: int = 180
ANIM_HOVER_MS: int = 80
ANIM_STAGGER_MS: int = 20
ANIM_FADE_MS: int = 120
ANIM_EASING: QEasingCurve.Type = QEasingCurve.Type.OutCubic
