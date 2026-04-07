"""Mixin providing side-panel slide animation for MainWindow."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QRect

from crucible.ui.side_panel_host import PANEL_DETAIL, PANEL_SETTINGS, PANEL_PROTON


class PanelAnimationMixin:
    """Slide-animation logic for the side-panel host.

    Expects the concrete class to have: ``_panel_host``, ``_panel_anim``,
    ``_margin_anim``, ``_panel_open``, ``_active_panel_key``,
    ``_return_panel_key``, ``nav_sidebar``, ``titlebar``,
    ``_current_panel_width``, ``_panel_width_for_key``, ``main_layout``,
    ``_panel_margin_right``, ``proton_panel``, ``_edit_panel_w``.
    """

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def _panel_geometry(self, open: bool) -> QRect:
        """Compute the target rectangle for the side panel."""
        c = self.centralWidget()
        tb = self.titlebar.height()
        h = c.height() - tb - 1
        w = self._current_panel_width() if open else self._panel_width_for_key(self._active_panel_key)
        x_open = c.width() - w
        x_closed = c.width()
        return QRect(x_open if open else x_closed, tb, w, h)

    def _set_panel_context(self) -> None:
        """Sync sidebar highlight and titlebar gap to the active panel."""
        self.nav_sidebar.set_active(
            self._active_panel_key if self._active_panel_key in (PANEL_SETTINGS, PANEL_PROTON) else None,
        )
        self._sync_titlebar_seam()

    # ------------------------------------------------------------------
    # Margin animation
    # ------------------------------------------------------------------

    def _animate_panel_margin(self, end_value: int) -> None:
        """Animate the right content margin to *end_value*."""
        self._margin_anim.stop()
        self._margin_anim.setStartValue(self.main_layout.contentsMargins().right())
        self._margin_anim.setEndValue(end_value)
        self._margin_anim.start()

    # ------------------------------------------------------------------
    # Show / hide
    # ------------------------------------------------------------------

    def _show_panel(self, key: str, *, on_open: Callable[[], None] | None = None, return_to: str | None = None) -> None:
        """Open (or switch to) the panel identified by *key*."""
        previous_key = self._active_panel_key
        self._active_panel_key = key
        self._return_panel_key = return_to if return_to != key else None
        self._panel_host.set_active_panel(key)
        if on_open:
            on_open()

        end = self._panel_geometry(True)
        if not self._panel_open:
            self._panel_open = True
            start = self._panel_geometry(False)
            self._panel_host.setGeometry(start)
            self._panel_host.show()
            self._panel_host.raise_()
            self._panel_anim.stop()
            try:
                self._panel_anim.finished.disconnect(self._on_panel_hidden)
            except (RuntimeError, TypeError):
                pass
            self._panel_anim.setStartValue(start)
            self._panel_anim.setEndValue(end)
            self._panel_anim.start()
            self._animate_panel_margin(self._current_panel_width())
            self._set_panel_context()
            return

        start = self._panel_host.geometry()
        self._panel_anim.stop()
        try:
            self._panel_anim.finished.disconnect(self._on_panel_hidden)
        except (RuntimeError, TypeError):
            pass
        self._panel_anim.setStartValue(start)
        self._panel_anim.setEndValue(end)
        self._panel_anim.start()
        self._animate_panel_margin(self._current_panel_width())
        self._set_panel_context()
        if previous_key != key:
            self._panel_host.raise_()

    def _restore_or_close_panel(self) -> None:
        """Return to the previous panel, or close all panels."""
        if self._return_panel_key:
            return_key = self._return_panel_key
            self._return_panel_key = None
            self._show_panel(return_key)
            return
        self._close_side_panel()

    def _close_side_panel(self) -> None:
        """Slide the side panel off-screen."""
        if not self._panel_open:
            return
        self._panel_open = False
        self._return_panel_key = None
        self.nav_sidebar.set_active(None)
        self._sync_titlebar_seam()

        start = self._panel_host.geometry()
        end = self._panel_geometry(False)
        self._panel_anim.stop()
        try:
            self._panel_anim.finished.disconnect(self._on_panel_hidden)
        except (RuntimeError, TypeError):
            pass
        self._panel_anim.setStartValue(start)
        self._panel_anim.setEndValue(end)
        self._panel_anim.finished.connect(self._on_panel_hidden)
        self._panel_anim.start()
        self._animate_panel_margin(0)

    def _toggle_content_panel(self, key: str, *, on_open: Callable[[], None] | None = None) -> None:
        """Toggle a content panel open/closed, tracking return state."""
        if self._panel_open and self._active_panel_key == key:
            self._restore_or_close_panel()
            return
        return_to = self._return_panel_key
        if return_to is None and self._panel_open and self._active_panel_key == PANEL_DETAIL and key in (PANEL_SETTINGS, PANEL_PROTON):
            return_to = PANEL_DETAIL
        self._show_panel(key, on_open=on_open, return_to=return_to)

    def toggle_settings(self) -> None:
        """Toggle the settings side panel."""
        self._toggle_content_panel(PANEL_SETTINGS)

    def toggle_proton(self) -> None:
        """Toggle the Proton management side panel."""
        self._toggle_content_panel(PANEL_PROTON, on_open=self.proton_panel.open)

    def _slide_panel(self, open: bool) -> None:
        """Slide the detail panel open or closed."""
        if open:
            self._show_panel(PANEL_DETAIL)
            return
        self._close_side_panel()

    def _on_panel_hidden(self) -> None:
        """Clean up after the close animation finishes."""
        try:
            self._panel_anim.finished.disconnect(self._on_panel_hidden)
        except (RuntimeError, TypeError):
            pass
        if not self._panel_open:
            self._panel_host.hide()
            self._active_panel_key = None
            self._set_panel_context()
