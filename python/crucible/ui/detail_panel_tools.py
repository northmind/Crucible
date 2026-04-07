from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil
import subprocess

from PyQt6.QtCore import QTimer

from crucible.core.paths import clean_env


class ToolsMixin:
    """Mixin for GameDetailPanel handling winetricks, shortcuts, and danger actions."""

    def _get_winetricks_context(self) -> tuple[str, str]:
        prefix = self._e_prefix.text().strip() if hasattr(self, '_e_prefix') else ''
        if not prefix:
            name = self._e_name.text().strip() if hasattr(self, '_e_name') else self._game.get('name', '')
            prefix = str(self._game_manager.get_default_prefix_path(name))
        checked = self._proton_group.checkedButton() if self._proton_group else None
        return prefix, (checked.text() if checked else '')

    def _on_winetricks_toggled(self, checked: bool) -> None:
        if checked:
            prefix, proton_name = self._get_winetricks_context()
            proc = self._game_manager.launch_winetricks(prefix, proton_name)
            if proc:
                self._wt_proc = proc
                if not hasattr(self, '_wt_timer'):
                    self._wt_timer = QTimer(self)
                    self._wt_timer.setInterval(1000)
                    self._wt_timer.timeout.connect(self._poll_winetricks)
                self._wt_timer.start()
            else:
                self._wt_row.setChecked(False)
                self.notification_requested.emit('Winetricks', 'failed to launch winetricks', 'error')
            return
        self._stop_winetricks()

    def _poll_winetricks(self) -> None:
        if self._wt_proc and self._wt_proc.poll() is not None:
            self._wt_proc = None
            self._wt_timer.stop()
            if self._wt_row is not None:
                self._wt_row.setChecked(False)

    def _stop_winetricks(self) -> None:
        if hasattr(self, '_wt_timer'):
            self._wt_timer.stop()
        if self._wt_proc:
            try:
                self._wt_proc.terminate()
            except ProcessLookupError:
                pass
            self._wt_proc = None
        if getattr(self, '_wt_row', None) is not None:
            self._wt_row.setChecked(False)

    def _on_shortcut_action(self) -> None:
        has_shortcut = self._game_manager.has_game_shortcut(self._game.get('name', ''))
        if has_shortcut:
            self._game_manager.remove_game_shortcut(self._game.get('name', ''))
            self._rebuild_view()
            return

        success, result = self._game_manager.create_game_shortcut(self._game)
        if not success:
            self.notification_requested.emit('Desktop Shortcut', f'failed: {result}', 'error')
            return
        self._rebuild_view()

    def _open_shortcuts_folder(self) -> None:
        subprocess.Popen(
            ['xdg-open', str(Path.home() / '.local/share/applications')],
            env=clean_env(),
            start_new_session=True,
        )

    def _dismiss_confirm_bar(self, *_: object) -> None:
        if self._confirm_bar.isVisible():
            self._confirm_bar._dismiss()

    def _on_danger_row(self, label: str, action: Callable[[], None]) -> None:
        if self._confirm_bar.isVisible() and self._confirm_bar._message == label:
            self._confirm_bar._dismiss()
            return
        self._confirm_bar.prompt(label, lambda: self._confirm_bar.prompt('are you sure', action))

    def _do_delete_game(self) -> None:
        if self._game_manager.delete_game(self._game.get('name', '')):
            self.closed.emit()
            self.game_deleted.emit()

    def _do_reset_prefix(self) -> None:
        self._game_manager.reset_game_prefix(self._game.get('name', ''))

    def _do_clear_logs(self) -> None:
        self._game_manager.clear_game_logs(self._game.get('name', ''))
        self._rebuild_view()

    def _do_remove_umu(self) -> None:
        shutil.rmtree(str(Path.home() / '.local/share/umu'), ignore_errors=True)
