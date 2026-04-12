from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QEnterEvent, QMouseEvent, QPainter, QPaintEvent, QPolygon, QContextMenuEvent
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy

from crucible.core.types import GameDict
from crucible.ui.styles import get_text_colors
from crucible.ui import styles
from crucible.ui.theme_system import animations_enabled, get_bg, get_selection_colors
from crucible.ui.color_utils import mix_hex
from crucible.ui.tokens import ANIM_EASING, ANIM_HOVER_MS, ROW_HEIGHT, SPACE_MD
from crucible.ui.widgets import init_styled


_ROW = ROW_HEIGHT
_SIZE_WORKERS = max(1, min(4, (os.cpu_count() or 1)))


def _format_size(total: int) -> str:
    if total < 1024 ** 2:
        return f"{total / 1024:.0f} KB"
    if total < 1024 ** 3:
        return f"{total / 1024 ** 2:.1f} MB"
    return f"{total / 1024 ** 3:.1f} GB"


def _compute_install_size(install_dir: str) -> str:
    try:
        total = 0
        for dirpath, _, filenames in os.walk(install_dir):
            for filename in filenames:
                try:
                    total += Path(dirpath, filename).stat().st_size
                except OSError:
                    continue
        return _format_size(total)
    except OSError:
        return "\u2014"


class _PlayBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(24, _ROW)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tc = get_text_colors()
        self._col     = tc.text_dim
        self._hover   = tc.text
        self._hovered = False
        self._stop    = False

    def set_colors(self, col: str, hover: str) -> None:
        self._col   = col
        self._hover = hover
        self.update()

    def set_stop(self, stop: bool) -> None:
        self._stop = stop
        self.update()

    def paintEvent(self, _: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._hover if self._hovered else self._col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        cx = self.width()  // 2
        cy = self.height() // 2
        if self._stop:
            s = 7
            p.drawRect(cx - s // 2, cy - s // 2, s, s)
        else:
            p.drawPolygon(QPolygon([
                QPoint(cx - 4, cy - 6),
                QPoint(cx - 4, cy + 6),
                QPoint(cx + 5, cy),
            ]))
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEnterEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)


class _EmptyLibrarySurface(QWidget):
    browse_requested = pyqtSignal()

    def __init__(self, accent_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        init_styled(self, "EmptyLibrarySurface")
        self._build_ui()
        self.refresh_styles()

    def _build_ui(self) -> None:
        from PyQt6.QtWidgets import QVBoxLayout

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 36, 36, 36)
        root.setSpacing(10)
        root.addStretch(1)

        self._title = QLabel("no games in library")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._title)

        self._subtitle = QLabel("drop an .exe anywhere in this window to add one")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._subtitle)

        root.addStretch(1)

    def set_accent(self, color: str) -> None:
        self._accent_color = color
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet('background: transparent;')
        self._title.setStyleSheet(styles.mono_label(dim=False, size="12pt", bold=True))
        self._subtitle.setStyleSheet(styles.mono_label())


class GameItemWidget(QWidget):
    selected       = pyqtSignal(dict)
    launch_clicked = pyqtSignal(dict)
    stop_clicked   = pyqtSignal(dict)

    def __init__(self, game_data: GameDict, accent_color: str) -> None:
        super().__init__()
        self.game_data    = game_data
        self.accent_color = accent_color
        self._running     = False
        self._selected    = False
        init_styled(self, 'GameItemWidget')

        tc = get_text_colors()
        self._text_color = tc.text
        self._dim_color  = tc.text_dim

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_MD, 0, SPACE_MD, 0)
        layout.setSpacing(0)

        self._name_label = QLabel(game_data.get('name', 'Unknown'))
        self._name_label.setStyleSheet(
            styles.mono_label(dim=False, extra=f"color: {self._text_color};")
        )
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._name_label)

        proton = game_data.get('proton_version', '') or '\u2014'
        if proton.lower().startswith('proton-'):
            proton = proton[7:]
        self._runner_label = QLabel(proton)
        self._runner_label.setFixedWidth(100)
        self._runner_label.setStyleSheet(
            styles.mono_label(extra=f"color: {self._dim_color};")
        )
        layout.addWidget(self._runner_label)

        self._col_size_label = QLabel('\u2014')
        self._col_size_label.setFixedWidth(92)
        self._col_size_label.setContentsMargins(30, 0, 0, 0)
        self._col_size_label.setStyleSheet(
            styles.mono_label(extra=f"color: {self._dim_color};")
        )
        layout.addWidget(self._col_size_label)

        self._play_btn = _PlayBtn(self)
        self._play_btn.set_colors(self._dim_color, accent_color)
        self._play_btn.clicked.connect(self._on_action)
        layout.addWidget(self._play_btn)

        # Hover animation: interpolates 0.0→1.0 over ANIM_HOVER_MS
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setStartValue(0.0)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.setDuration(ANIM_HOVER_MS)
        self._hover_anim.setEasingCurve(ANIM_EASING)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

    @property
    def is_running(self) -> bool:
        """Whether this game item is currently shown in the running state."""
        return self._running

    def set_running(self, running: bool) -> None:
        """Update the visual running state of this game item."""
        if self._running == running:
            return
        self._running = running
        self._play_btn.set_stop(running)
        if running:
            self._play_btn.set_colors(self.accent_color, self.accent_color)
            self._name_label.setStyleSheet(
                styles.mono_label(dim=False, bold=True, extra=f"color: {self.accent_color};")
            )
        else:
            self._play_btn.set_colors(self._dim_color, self.accent_color)
            self._name_label.setStyleSheet(
                styles.mono_label(dim=False, extra=f"color: {self._text_color};")
            )

    def set_size(self, size_str: str) -> None:
        """Update the displayed install size text."""
        self._col_size_label.setText(size_str)

    def set_selected(self, selected: bool) -> None:
        """Mark this item as selected or deselected and refresh its background."""
        self._selected = selected
        self._refresh_bg()

    def _on_action(self) -> None:
        if self._running:
            self.stop_clicked.emit(self.game_data)
        else:
            self.launch_clicked.emit(self.game_data)

    def _refresh_bg(self) -> None:
        sel = get_selection_colors()
        if self._selected:
            self.setStyleSheet(
                f"QWidget#GameItemWidget {{ background-color: {sel.selection_bg};"
                f" border-left: 2px solid {sel.nav_accent}; border-radius: 0px; }}"
            )
        else:
            self.setStyleSheet(
                "QWidget#GameItemWidget { background-color: transparent;"
                " border-left: 2px solid transparent; border-radius: 0px; }"
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit the selected signal on left-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.game_data)
            event.accept()
        else:
            super().mousePressEvent(event)

    def contextMenuEvent(self, _event: QContextMenuEvent) -> None:
        """Select this item when the context menu is requested."""
        self.selected.emit(self.game_data)

    def _on_hover_step(self, t: float) -> None:
        """Apply interpolated hover background at progress *t* (0.0–1.0)."""
        if self._selected:
            return
        bg = get_bg()
        sel = get_selection_colors()
        hover_tint = mix_hex(bg.bg, sel.nav_accent, 0.08 * t)
        self.setStyleSheet(
            f"QWidget#GameItemWidget {{ background-color: {hover_tint};"
            " border-left: 2px solid transparent; border-radius: 0px; }"
        )

    def enterEvent(self, event: QEnterEvent) -> None:
        """Animate hover-in (or apply instantly when animations are disabled)."""
        if not self._selected:
            if animations_enabled():
                self._hover_anim.setDirection(QVariantAnimation.Direction.Forward)
                self._hover_anim.start()
            else:
                self._on_hover_step(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEnterEvent) -> None:
        """Animate hover-out (or restore instantly when animations are disabled)."""
        if animations_enabled() and not self._selected:
            self._hover_anim.setDirection(QVariantAnimation.Direction.Backward)
            self._hover_anim.start()
        else:
            self._refresh_bg()
        super().leaveEvent(event)
