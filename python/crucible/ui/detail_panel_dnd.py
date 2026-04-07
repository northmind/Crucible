from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent


class DragDropMixin:
    """Mixin for GameDetailPanel handling zip drag-and-drop events."""

    def _first_zip_path(self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> str:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.zip'):
                return path
        return ''

    def _handle_zip_drag_event(self, event: QDragEnterEvent | QDragMoveEvent) -> bool:
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith('.zip') for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            self.zip_drag_preview.emit(True, self._first_zip_path(event))
            return True
        self.zip_drag_preview.emit(False, '')
        event.ignore()
        return False

    def _handle_zip_drop_event(self, event: QDropEvent) -> bool:
        self.zip_drag_preview.emit(False, '')
        if not self._game:
            event.ignore()
            return False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.zip'):
                self.zip_drop.emit(self._game, path)
                event.acceptProposedAction()
                return True
        event.ignore()
        return False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept drag/drop events on artwork and scroll child widgets."""
        if watched in {
            self._art,
            self._art_image,
            self._art_notice,
            self._scroll.viewport(),
            self._scroll.widget(),
            self._zip_import_bar,
        }:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                if self._handle_zip_drag_event(event):
                    return True
            elif event.type() == QEvent.Type.DragLeave:
                self.zip_drag_preview.emit(False, '')
                return True
            elif event.type() == QEvent.Type.Drop:
                if self._handle_zip_drop_event(event):
                    return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept and preview zip files when dragged onto the panel."""
        self._handle_zip_drag_event(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Continue accepting zip drag while the cursor moves over the panel."""
        self._handle_zip_drag_event(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Emit zip_drag_preview(False) when the drag leaves the panel."""
        self.zip_drag_preview.emit(False, '')
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle a zip file drop on the panel and emit zip_drop."""
        self._handle_zip_drop_event(event)
