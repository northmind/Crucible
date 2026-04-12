from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog, QDialog, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from crucible.ui import styles
from crucible.ui.tokens import ICON_BTN_SIZE, SPACE_MD, SPACE_LG


# ---------------------------------------------------------------------------
# Widget factory helpers
# ---------------------------------------------------------------------------


def init_styled(widget: QWidget, name: str) -> None:
    """Set *name* as the Qt object name and enable stylesheet backgrounds."""
    widget.setObjectName(name)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def make_scroll_page(
    *,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    spacing: int = 0,
    accent: str | None = None,
) -> QScrollArea:
    """Create a frameless QScrollArea with a transparent inner QWidget and QVBoxLayout.

    Access the inner layout via ``scroll.widget().layout()``.
    """
    scroll = QScrollArea()
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(styles.scroll_area(accent=accent) if accent else
                         "background: transparent; border: none;")
    scroll.viewport().setAutoFillBackground(False)
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    scroll.setWidget(inner)
    return scroll


def make_divider() -> QLabel:
    """Create a 1px-tall themed separator line."""
    sep = QLabel()
    sep.setFixedHeight(1)
    sep.setStyleSheet(styles.divider())
    return sep


def make_flat_button(
    text: str,
    *,
    size: tuple[int, int] | None = None,
    qss: str = "",
) -> QPushButton:
    """Create a flat QPushButton with pointer cursor and optional fixed size.

    The caller is responsible for connecting signals and applying final QSS
    via ``setStyleSheet`` if *qss* is empty.
    """
    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if size is not None:
        btn.setFixedSize(*size)
    if qss:
        btn.setStyleSheet(qss)
    return btn

# ---------------------------------------------------------------------------
# Sliding overlay base
# ---------------------------------------------------------------------------


class SlidingOverlay(QWidget):
    """Base class for bottom-anchored overlays that slide up/down.

    Subclasses must call ``_init_slide(duration_ms)`` after ``super().__init__``
    and implement ``_build_ui()`` / ``refresh_colors()``.  Override
    ``_bar_height()`` for dynamic-height overlays (default: ``self.height()``).
    """

    _X_OFFSET = 1  # left pixel inset from parent edge

    def _init_slide(self, duration_ms: int = 160) -> None:
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(duration_ms)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()

    # -- helpers subclasses may override ------------------------------------

    def _bar_height(self) -> int:
        """Return the current bar height used for slide calculations."""
        return self.height()

    def _on_slide_width(self, width: int) -> None:
        """Called when the bar width changes during slide/reposition.

        Override to sync child widgets (e.g. progress bar) to the new width.
        """

    def _on_hidden(self) -> None:
        """Called after the dismiss animation finishes and the widget hides.

        Override to reset internal state (e.g. progress bars).
        """
        self.hide()

    # -- slide mechanics ----------------------------------------------------

    def _prep_anim(self) -> None:
        """Stop the running animation and disconnect finished signal."""
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass

    def _slide_up(self) -> None:
        p_w, p_h = self.parent().width(), self.parent().height()
        w = p_w - self._X_OFFSET
        self.setFixedWidth(w)
        self._on_slide_width(w)
        self._prep_anim()
        target = QPoint(self._X_OFFSET, p_h - self._bar_height())
        if not self.isVisible():
            self.move(self._X_OFFSET, p_h)
            self.show()
            self.raise_()
        if self.pos() == target:
            return
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(target)
        self._anim.start()

    def _slide_down(self) -> None:
        p_h = self.parent().height()
        self._prep_anim()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self._X_OFFSET, p_h))
        self._anim.finished.connect(self._on_hidden)
        self._anim.start()

    def reposition(self, parent_w: int, parent_h: int) -> None:
        w = parent_w - self._X_OFFSET
        self.setFixedWidth(w)
        self._on_slide_width(w)
        if self.isVisible():
            self.move(self._X_OFFSET, parent_h - self._bar_height())


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
