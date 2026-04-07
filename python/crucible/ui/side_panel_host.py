from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from crucible.ui import styles

# Panel key constants used across main_window, panel_animation, game_events,
# nav_sidebar, and detail_panel to avoid stringly-typed dispatch.
PANEL_DETAIL = 'detail'
PANEL_SETTINGS = 'settings'
PANEL_PROTON = 'proton'


class SidePanelHost(QWidget):
    """Stacked container that hosts side panels (detail, settings, proton)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidePanelHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._stack = QStackedWidget()
        self._stack.setObjectName("SidePanelStack")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack)
        self._panels: dict[str, QWidget] = {}
        self._active_key: str | None = None
        self._apply_style()
        self.hide()

    def _apply_style(self) -> None:
        """Apply border and background styling from the current theme."""
        edge = styles.line_accent()
        fill = styles.panel_fill()
        self.setStyleSheet(
            f"#SidePanelHost {{ background: {fill}; border-left: 1px solid {edge};"
            f" border-right: 1px solid {edge}; }}"
            "#SidePanelStack { background: transparent; border: none; }"
        )

    def add_panel(self, key: str, widget: QWidget) -> None:
        """Register a panel widget under the given key."""
        self._panels[key] = widget
        self._stack.addWidget(widget)

    def set_active_panel(self, key: str) -> None:
        """Switch to the panel registered under *key* and show the host."""
        widget = self._panels[key]
        self._active_key = key
        self._stack.setCurrentWidget(widget)
        self.show()
        self.raise_()

    def current_key(self) -> str | None:
        """Return the key of the currently active panel, or None."""
        return self._active_key

    def refresh_colors(self) -> None:
        """Re-apply styling after a theme change."""
        self._apply_style()
