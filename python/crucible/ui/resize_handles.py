from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QWidget

HANDLE_WIDTH = 6

_EDGE_MAP = {
    "left": Qt.Edge.LeftEdge,
    "right": Qt.Edge.RightEdge,
    "top": Qt.Edge.TopEdge,
    "bottom": Qt.Edge.BottomEdge,
    "top_left": Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
    "top_right": Qt.Edge.RightEdge | Qt.Edge.TopEdge,
    "bottom_left": Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
    "bottom_right": Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
}

_CURSOR_MAP = {
    "left": Qt.CursorShape.SizeHorCursor,
    "right": Qt.CursorShape.SizeHorCursor,
    "top": Qt.CursorShape.SizeVerCursor,
    "bottom": Qt.CursorShape.SizeVerCursor,
    "top_left": Qt.CursorShape.SizeFDiagCursor,
    "top_right": Qt.CursorShape.SizeBDiagCursor,
    "bottom_left": Qt.CursorShape.SizeBDiagCursor,
    "bottom_right": Qt.CursorShape.SizeFDiagCursor,
}

_EDGE_NAMES = [
    "top_left", "top_right", "bottom_left", "bottom_right",
    "left", "right", "top", "bottom",
]


class ResizeHandle(QWidget):
    """Invisible edge/corner widget that initiates a system window resize."""

    def __init__(self, edge_name: str, main_window: QWidget) -> None:
        super().__init__(main_window)
        self.edge_name = edge_name
        self.main_window = main_window
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start a system resize when the left mouse button is pressed."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        edge = _EDGE_MAP.get(self.edge_name, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        window = self.main_window.windowHandle()
        if window and window.startSystemResize(edge):
            event.accept()


def setup_resize_handles(window: QWidget) -> dict[str, ResizeHandle]:
    """Create eight resize handles (four edges + four corners) on *window*."""
    handles: dict[str, ResizeHandle] = {}
    for name in _EDGE_NAMES:
        handle = ResizeHandle(name, window)
        cursor = _CURSOR_MAP.get(name, Qt.CursorShape.ArrowCursor)
        handle.setCursor(cursor)
        handles[name] = handle
    return handles


def update_resize_handles(handles: dict[str, ResizeHandle], w: int, h: int) -> None:
    """Reposition resize handles to match the current window dimensions."""
    hw = HANDLE_WIDTH
    if "top_left" in handles:
        handles["top_left"].setGeometry(0, 0, hw, hw)
    if "top_right" in handles:
        handles["top_right"].setGeometry(w - hw, 0, hw, hw)
    if "bottom_left" in handles:
        handles["bottom_left"].setGeometry(0, h - hw, hw, hw)
    if "bottom_right" in handles:
        handles["bottom_right"].setGeometry(w - hw, h - hw, hw, hw)
    if "left" in handles:
        handles["left"].setGeometry(0, hw, hw, h - 2 * hw)
    if "right" in handles:
        handles["right"].setGeometry(w - hw, hw, hw, h - 2 * hw)
    if "top" in handles:
        handles["top"].setGeometry(hw, 0, w - 2 * hw, hw)
    if "bottom" in handles:
        handles["bottom"].setGeometry(hw, h - hw, w - 2 * hw, hw)
