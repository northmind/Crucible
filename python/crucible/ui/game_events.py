"""Mixin providing game-related event handlers for MainWindow."""
from __future__ import annotations

from crucible.core.types import GameDict
from crucible.ui.side_panel_host import PANEL_DETAIL


class GameEventsMixin:
    """Handlers for game selection, launch, stop, and update signals.

    Expects the concrete class to have: ``detail_panel``, ``game_manager``,
    ``library_widget``, ``_panel_open``, ``_active_panel_key``,
    ``_return_panel_key``, ``_slide_panel``, ``_panel_host``,
    ``_panel_geometry``, ``_panel_margin_right``, ``_apply_main_layout_margins``,
    ``_sync_titlebar_seam``, ``_edit_panel_w``.
    """

    def _on_game_selected(self, game: GameDict) -> None:
        """Open the detail panel for the selected game."""
        self.detail_panel.show_game(game)
        is_running = self.game_manager.is_game_running(game['name'])
        self.detail_panel.set_running(is_running)
        self._slide_panel(True)

    def _close_detail(self) -> None:
        """Deselect the current game and close the detail panel."""
        self.library_widget.clear_selection()
        if self._active_panel_key == PANEL_DETAIL:
            self._slide_panel(False)
        else:
            self._return_panel_key = None

    def _on_running_state_changed(self, game_name: str, is_running: bool) -> None:
        """Update the detail panel when a game starts or stops."""
        game = self.detail_panel._game
        if game and game['name'] == game_name:
            self.detail_panel.set_running(is_running)

    def _on_game_launch(self, game: GameDict) -> None:
        """Attempt to launch a game; show errors in the detail panel."""
        self.detail_panel.clear_launch_error()
        error = self.game_manager.launch_game(game['name'])
        if error:
            self.library_widget.select_game(game['name'])
            self.detail_panel.show_game(game)
            self.detail_panel.set_running(False)
            self._slide_panel(True)
            self.detail_panel.show_launch_error("Launch Failed", error)

    def _on_game_stop(self, game: GameDict) -> None:
        """Request the game manager to stop a running game."""
        self.game_manager.stop_game(game['name'])

    def _on_game_updated(self) -> None:
        """Refresh the library after a game config change.

        The manager methods (add_game, _update_game_record, rename_game)
        already call scan_games() internally, so only a UI refresh is needed.
        """
        self.library_widget.refresh()

    def _on_game_deleted(self) -> None:
        """Refresh the library after a game is removed."""
        self.library_widget.refresh()

    def _on_install_dir_resolved(self, game_name: str, install_dir: str) -> None:
        """Persist an auto-detected install directory for a game."""
        game = self.game_manager.get_game(game_name)
        if not game or game.get('exe_match_mode') == 'custom':
            return
        if self.game_manager.update_install_dir(game_name, install_dir):
            self.library_widget.invalidate_size(game_name)
            self.library_widget.schedule_refresh()
            if self._panel_open and self.detail_panel._game and \
                    self.detail_panel._game.get('name') == game_name:
                updated = self.game_manager.get_game(game_name)
                if updated:
                    self.detail_panel.show_game(updated)

    def _on_panel_width_changed(self, w: int) -> None:
        """Adjust layout when the detail panel changes width."""
        self._edit_panel_w = w
        if self._panel_open and self._active_panel_key == PANEL_DETAIL:
            self._panel_host.setGeometry(self._panel_geometry(True))
            self._panel_margin_right = w
            self._apply_main_layout_margins()
            self._sync_titlebar_seam()
