from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget

from crucible.ui.styles import get_text_colors, line_accent_rgba, shell_fill
from crucible.ui import styles
from crucible.ui.theme_system import get_selection_colors


class ArtworkMixin:
    """Mixin for GameDetailPanel handling artwork scaling and notice overlay."""

    def _apply_artwork_scale(self) -> None:
        art: QWidget = self._art
        inset = QRect(1, 0, max(0, art.width() - 2), max(0, art.height()))
        pixmap: QPixmap = self._artwork_pixmap
        if pixmap.isNull():
            self._art_image.clear()
            self._art_image.setGeometry(inset)
            return
        target = inset.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        from PyQt6.QtCore import Qt

        scaled = pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = inset.x() + max(0, (inset.width() - scaled.width()) // 2)
        self._art_image.setGeometry(QRect(x, inset.y(), scaled.width(), scaled.height()))
        self._art_image.setPixmap(scaled)

    def _art_notice_hidden_pos(self) -> QPoint:
        return QPoint(self._art.width(), 0)

    def _show_art_notice(self) -> None:
        self._art_notice_anim.stop()
        try:
            self._art_notice_anim.finished.disconnect(self._art_notice.hide)
        except (RuntimeError, TypeError):
            pass
        self._art_notice.setGeometry(0, 0, self._art.width(), self._art.height())
        if not self._art_notice_visible:
            self._art_notice.move(self._art_notice_hidden_pos())
        self._art_notice.show()
        self._art_notice.raise_()
        self._art_notice_anim.setStartValue(self._art_notice.pos())
        self._art_notice_anim.setEndValue(QPoint(0, 0))
        self._art_notice_anim.start()
        self._art_notice_visible = True

    def _hide_art_notice(self) -> None:
        self._art_notice_anim.stop()
        try:
            self._art_notice_anim.finished.disconnect(self._art_notice.hide)
        except (RuntimeError, TypeError):
            pass
        if not self._art_notice_visible:
            self._art_notice.hide()
            return
        self._art_notice_anim.setStartValue(self._art_notice.pos())
        self._art_notice_anim.setEndValue(self._art_notice_hidden_pos())
        self._art_notice_anim.finished.connect(self._art_notice.hide)
        self._art_notice_anim.start()
        self._art_notice_visible = False

    def _set_art_notice_content(self, title: str, message: str) -> None:
        self._art_notice_title.setText(title.lower())
        self._art_notice_message.setText(message.lower())
        self._apply_art_notice_style()

    def _apply_art_notice_style(self) -> None:
        accent = get_selection_colors().nav_accent
        tint = line_accent_rgba(132)
        fill = shell_fill()
        self._art_notice.setStyleSheet(
            f"#DetailArtNotice {{ background: {fill}; border-left: 2px solid {accent}; border-bottom: 1px solid {tint}; }}"
        )
        self._art_notice_title.setStyleSheet(styles.mono_label(dim=False, bold=True))
        self._art_notice_message.setStyleSheet(styles.mono_label())

    def show_launch_error(self, title: str, message: str) -> None:
        """Show a titled error message in the art notice overlay."""
        self._zip_drag_active = False
        self._art_mode = 'message'
        self._set_art_notice_content(title, message)
        self._show_art_notice()

    def clear_launch_error(self) -> None:
        """Hide the art notice overlay and restore artwork display."""
        if self._zip_drag_active:
            self.clear_zip_drag_notice()
            return
        self._art_mode = 'artwork'
        self._hide_art_notice()
        self._apply_artwork_scale()

    def show_zip_drag_notice(self, zip_path: str) -> None:
        """Show the zip import bar for a dragged zip file at *zip_path*."""
        self._zip_drag_active = True
        self._zip_import_bar.show_file(zip_path)

    def clear_zip_drag_notice(self) -> None:
        """Hide the zip import bar and reset drag state."""
        self._zip_drag_active = False
        self._zip_import_bar.dismiss()

    def _on_artwork_ready(self, game_name: str, pixmap: QPixmap) -> None:
        if not self._game or self._game['name'] != game_name or pixmap.isNull():
            return
        self._artwork_pixmap = pixmap
        self._apply_artwork_scale()
