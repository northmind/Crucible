"""Pure color math utilities — no Qt or theme dependencies."""

from __future__ import annotations

import re

_HEX_COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a hex color string to an (r, g, b) tuple."""
    value = value.lstrip("#")
    if not _HEX_COLOR_RE.match(value):
        raise ValueError(f"Invalid hex color: #{value}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix_hex(a_hex: str, b_hex: str, amount: float) -> str:
    """Linearly interpolate between two hex colors by *amount* (0.0–1.0)."""
    amount = max(0.0, min(1.0, amount))
    ar, ag, ab = hex_to_rgb(a_hex)
    br, bg, bb = hex_to_rgb(b_hex)
    r = round(ar + (br - ar) * amount)
    g = round(ag + (bg - ag) * amount)
    b = round(ab + (bb - ab) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"

def validate_hex(value: str) -> str:
    """Validate and normalize a hex color string, raising ValueError if invalid."""
    stripped = value.lstrip("#")
    if not _HEX_COLOR_RE.match(stripped):
        raise ValueError(f"Invalid hex color: {value}")
    return f"#{stripped.lower()}"
