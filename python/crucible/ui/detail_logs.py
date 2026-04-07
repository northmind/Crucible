from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from crucible.core.paths import Paths, clean_env
from crucible.ui.styles import get_accent, get_text_colors
from crucible.ui.theme_system import get_selection_colors


def build_logs_section(game: dict[str, str]) -> QWidget:
    """Build the logs section showing the two most recent game log files."""
    accent = get_accent()
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(0)

    name = game.get('name', '')
    logs = sorted(
        Paths.game_logs_dir(name).glob('*.log'),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )

    visible_logs = logs[:2]
    if not visible_logs:
        lbl = QLabel("no logs yet")
        lbl.setContentsMargins(8, 8, 0, 0)
        lbl.setStyleSheet(f"color: {get_text_colors()['text_dim']}; background: transparent; font-family: 'Courier New', monospace; font-size: 8.5pt;")
        lbl.setFixedHeight(28)
        layout.addWidget(lbl)
        widget.setFixedHeight(44)
        return widget

    for log in visible_logs:
        layout.addWidget(make_log_entry_button(log, accent, label=log.stem))

    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    widget.setFixedHeight(40 if len(visible_logs) == 1 else 72)
    return widget


def make_log_entry_button(path: Path, accent: str, label: str) -> QPushButton:
    """Create a clickable button that opens the given log file via xdg-open."""
    try:
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        diff = datetime.now() - dt
        secs = diff.total_seconds()
        if secs < 60:
            rel = "just now"
        elif secs < 3600:
            rel = f"{int(secs // 60)}m ago"
        elif secs < 86400:
            rel = f"{int(secs // 3600)}h ago"
        else:
            rel = f"{diff.days}d ago"
        text = f"{label}  ·  {rel}"
    except OSError:
        text = label

    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    sel = get_selection_colors()
    btn.setStyleSheet(
        f"QPushButton {{ color: {get_text_colors()['text_dim']}; background: transparent; border: none;"
        f" text-align: left; font-family: 'Courier New', monospace; font-size: 8.5pt;"
        f" padding: 8px 8px; border-radius: 0px; }}"
        f"QPushButton:hover {{ color: {sel['selection_text']}; background: {sel['hover_bg']}; }}"
    )
    btn.clicked.connect(
        lambda _=False, p=path: subprocess.Popen(
            ['xdg-open', str(p)], env=clean_env(), start_new_session=True
        )
    )
    return btn
