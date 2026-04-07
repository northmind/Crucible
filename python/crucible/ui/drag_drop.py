"""Mixin providing drag-and-drop handling for MainWindow."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent

from crucible.core.types import GameDict


class DragDropMixin:
    """Exe and zip drag-and-drop support for the main window.

    Expects the concrete class to have: ``detail_panel``,
    ``_zip_drag_preview_active``, ``_drag_preview``, ``titlebar``,
    ``_add_game_from_path``, ``_show_notification``, ``game_manager``,
    ``library_widget``.
    """

    def _first_path_with_suffix(self, event: QDragEnterEvent | QDragMoveEvent, suffix: str) -> str:
        """Return the first dropped URL whose local path ends with *suffix*."""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(suffix):
                return path
        return ''

    def _drag_notice_anchor_y(self) -> int:
        """Vertical anchor for drag-preview notifications."""
        return self.titlebar.height() + 16

    def _show_drag_notice(self, mode: str, path: str, *, target_name: str = '') -> None:
        """Display an in-window drag preview for the given mode."""
        if not path:
            return
        if mode == 'zip':
            if not self._zip_drag_preview_active:
                self.detail_panel.show_zip_drag_notice(path)
                self._zip_drag_preview_active = True
            self._drag_preview.dismiss()
            return
        self._zip_drag_preview_active = False
        file_name = Path(path).name
        self.detail_panel.clear_zip_drag_notice()
        self._drag_preview.show_message(
            'import executable', file_name, 'info',
            anchor_y=self._drag_notice_anchor_y(), linger_ms=0,
        )
        self._drag_preview.raise_()

    def _hide_drag_notice(self) -> None:
        """Dismiss all drag preview overlays."""
        self._drag_preview.dismiss()
        if self._zip_drag_preview_active:
            self.detail_panel.clear_zip_drag_notice()
            self._zip_drag_preview_active = False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept the drag if it contains an .exe URL, showing a preview."""
        if event.mimeData().hasUrls():
            exe_path = self._first_path_with_suffix(event, '.exe')
            if exe_path:
                event.acceptProposedAction()
                self._show_drag_notice('exe', exe_path)
                return
        self._hide_drag_notice()
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Continue accepting the drag while an .exe URL is present."""
        exe_path = self._first_path_with_suffix(event, '.exe')
        if exe_path:
            event.acceptProposedAction()
            self._show_drag_notice('exe', exe_path)
            return
        self._hide_drag_notice()
        event.ignore()

    def dragLeaveEvent(self, _: QDragLeaveEvent) -> None:
        """Dismiss drag preview overlays when the cursor leaves the window."""
        self._hide_drag_notice()

    def dropEvent(self, event: QDropEvent) -> None:
        """Import the first .exe from the dropped URLs as a new game."""
        self._hide_drag_notice()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.exe'):
                self._add_game_from_path(path)
                break
        event.acceptProposedAction()

    def _on_zip_drag_preview(self, active: bool, zip_path: str) -> None:
        """Handle zip drag preview toggle from the detail panel."""
        if not active:
            self._hide_drag_notice()
            return
        self._show_drag_notice('zip', zip_path)

    def _on_zip_drop(self, game: GameDict, zip_path: str) -> None:
        """Extract a dropped zip into the game's install directory."""
        from crucible.core.zip import extract
        from crucible.core.paths import find_game_root

        exe_path = game.get('exe_path', '')
        extract_dir = game.get('install_dir') or find_game_root(exe_path) or str(Path(exe_path).parent)
        if not extract_dir:
            self._show_notification("No Directory", "No install directory set for this game.", "warning")
            return

        try:
            extracted = extract(zip_path, extract_dir)
            detected_dlls = extracted.dlls
            detected_exes = extracted.exes

            if detected_dlls:
                existing = {d.strip() for d in game.get('custom_overrides', '').split(',') if d.strip()}
                detected_set = set(detected_dlls)
                added = detected_set - existing
                if added:
                    merged = ','.join(sorted(existing | detected_set))
                    self.game_manager.update_custom_overrides(game, merged)

            detected_exe = detected_exes[0] if detected_exes else None
            if detected_exe and detected_exe != game.get('exe_path', ''):
                self.game_manager.update_exe_path(game, detected_exe, exe_match_mode='custom')

            if detected_dlls or detected_exe:
                self.library_widget.refresh()
                updated = self.game_manager.get_game(game['name'])
                if updated:
                    self.detail_panel.show_game(updated)

            self.detail_panel.show_extraction_result(detected_dlls or None, detected_exe)
        except (OSError, ValueError, RuntimeError) as e:
            if self._zip_drag_preview_active:
                self.detail_panel.clear_zip_drag_notice()
                self._zip_drag_preview_active = False
            self._show_notification("Extract Failed", str(e), "error")
