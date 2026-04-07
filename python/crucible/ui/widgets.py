from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QFileDialog, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from crucible.ui import styles
from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors

_FOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"'
    ' fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
    '</svg>'
)


def folder_icon(color: str, size: int = 13) -> QIcon:
    """Render a folder SVG icon as a QIcon with the given stroke color and pixel size."""
    from PyQt6.QtSvg import QSvgRenderer  # type: ignore[import-untyped]
    svg = _FOLDER_SVG.format(color=color).encode()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    QSvgRenderer(svg).render(p)
    p.end()
    return QIcon(pix)


def _make_file_dialog(parent: QWidget | None, title: str, start_dir: str) -> QFileDialog:
    dialog = QFileDialog(parent, title, start_dir)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    dialog.setStyleSheet(styles.file_dialog())
    dialog.setFont(QFont("Courier New", 10))
    return dialog


def get_executable_path(parent: QWidget | None = None) -> str | None:
    """Open a file dialog to select an .exe file, returning the path or None if cancelled."""
    dialog = _make_file_dialog(parent, "Select Game Executable", str(Path.home()))
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setNameFilters(["Executable files (*.exe)", "All files (*)"])
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selectedFiles()[0]
    return None


def get_directory_path(parent: QWidget | None = None, title: str = "Select Directory", start_dir: str | None = None) -> str | None:
    """Open a file dialog to select a directory, returning the path or None if cancelled."""
    dialog = _make_file_dialog(parent, title, start_dir or str(Path.home()))
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selectedFiles()[0]
    return None


_NOTICE_KIND = {
    "warning": {"color": "#e5c07b", "tint": "rgba(229, 192, 123, 0.12)", "symbol": "\u26a0"},
    "error": {"color": "#e06c75", "tint": "rgba(224, 108, 117, 0.12)", "symbol": "\u2715"},
    "info": {"color": None, "tint": None, "symbol": "\u2022"},
}


class SlidingNotification(QWidget):
    _WIDTH = 400
    _MARGIN = 16
    _SLIDE_MS = 180
    _LINGER_MS = 5000

    def __init__(self, parent: QWidget | None = None, *, show_close: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("SlidingNotification")
        self._show_close = show_close
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._anchor_y = self._MARGIN
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(self._SLIDE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.setInterval(self._LINGER_MS)
        self._linger.timeout.connect(self.dismiss)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._symbol = QLabel()
        header.addWidget(self._symbol)

        self._title = QLabel()
        header.addWidget(self._title, 1)

        self._close = QPushButton("×")
        self._close.setFlat(True)
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close.setFixedSize(18, 18)
        self._close.clicked.connect(self.dismiss)
        self._close.setVisible(self._show_close)
        header.addWidget(self._close)

        root.addLayout(header)

        self._message = QLabel()
        self._message.setWordWrap(True)
        root.addWidget(self._message)

        self.refresh_colors()

    def refresh_colors(self) -> None:
        """Reapply current theme colors to the notification widget."""
        self._apply_kind("info")

    def show_message(self, title: str, message: str, kind: str = "warning", *, anchor_y: int | None = None, linger_ms: int | None = None) -> None:
        """Slide in a notification with the given title, message, and kind ('warning', 'error', or 'info')."""
        if anchor_y is not None:
            self._anchor_y = anchor_y
        self._linger.stop()
        try:
            self._anim.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass

        self._apply_kind(kind)
        self._title.setText(title.lower())
        self._message.setText(message)

        parent = self.parentWidget()
        if parent is None:
            return

        available_width = max(240, min(self._WIDTH, parent.width() - self._MARGIN * 2))
        self.setFixedWidth(available_width)
        self.adjustSize()

        end = self._visible_pos()
        start = QPoint(parent.width() + self.width(), end.y())

        self._anim.stop()
        if not self.isVisible():
            self.move(start)
            self.show()
            self.raise_()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(end)
        self._anim.start()

        linger = self._LINGER_MS if linger_ms is None else linger_ms
        if linger > 0:
            self._linger.start(linger)

    def dismiss(self) -> None:
        """Animate the notification off-screen to the right and hide it."""
        self._linger.stop()
        if not self.isVisible():
            return
        try:
            self._anim.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass
        parent = self.parentWidget()
        if parent is None:
            self.hide()
            return
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(parent.width() + self.width(), self.y()))
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _visible_pos(self) -> QPoint:
        """Return the on-screen anchor point for the notification."""
        parent = self.parentWidget()
        if parent is None:
            return QPoint(0, self._anchor_y)
        x = parent.width() - self.width() - self._MARGIN
        return QPoint(x, self._anchor_y)

    def reposition(self, *, anchor_y: int | None = None) -> None:
        """Reposition the notification to its anchored location if currently visible."""
        if anchor_y is not None:
            self._anchor_y = anchor_y
        if not self.isVisible():
            return
        self.move(self._visible_pos())

    def _apply_kind(self, kind: str) -> None:
        spec = _NOTICE_KIND.get(kind, _NOTICE_KIND["warning"])
        bg = styles.get_bg()
        text = get_text_colors()
        selection = get_selection_colors()
        accent = spec["color"] or selection["nav_accent"]
        accent_color = QColor(accent)
        tint = spec["tint"] or f"rgba({accent_color.red()},{accent_color.green()},{accent_color.blue()},0.12)"

        self.setStyleSheet(
            f"#SlidingNotification {{"
            f" background-color: {bg['bg']};"
            f" border: 1px solid {bg['border']};"
            f" border-left: 3px solid {accent};"
            f" }}"
        )
        self._symbol.setText(spec["symbol"])
        self._symbol.setStyleSheet(
            f"color: {accent}; background: transparent; font-family: 'Courier New', monospace; font-size: 12pt;"
        )
        self._title.setStyleSheet(
            f"color: {text['text']}; background: transparent; font-family: 'Courier New', monospace; font-size: 9pt; font-weight: bold;"
        )
        self._message.setStyleSheet(
            f"color: {text['text_dim']}; background: transparent; font-family: 'Courier New', monospace; font-size: 9pt;"
        )
        self._close.setVisible(self._show_close)
        self._close.setStyleSheet(
            f"QPushButton {{ color: {text['text_dim']}; background: {tint}; border: none; font-family: 'Courier New', monospace; font-size: 10pt; }}"
            f"QPushButton:hover {{ color: {accent}; }}"
        )
