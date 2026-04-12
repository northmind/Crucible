from __future__ import annotations

from crucible.ui.theme_button import _ThemeBtn
from crucible.ui.theme_importer import (
    ThemeImportWorker,
    import_vscode_theme_snapshot,
    normalize_vscode_theme_slug,
)
from crucible.ui.theme_system import (
    Theme,
    apply_builtin_theme,
    apply_saved_imported_theme,
    builtin_themes,
    get_active_builtin_key,
    get_active_saved_theme_slug,
    list_saved_imported_themes,
    remove_saved_imported_theme,
    save_imported_theme,
    theme_from_import_palette,
)

_THEME_DESCRIPTIONS = {
    "crucible": "by Nakama",
    "high-contrast": "WCAG AAA · high visibility",
}


class SettingsThemeMixin:
    """Theme selection, import, and removal logic for SettingsPanel."""

    def _sync_from_settings(self) -> None:
        self._saved_themes = list_saved_imported_themes()
        self._selected_saved_slug = get_active_saved_theme_slug()
        if self._selected_saved_slug:
            self._selected_theme = None
        else:
            active_key = get_active_builtin_key()
            self._selected_theme = next(
                (theme for theme in builtin_themes() if theme.key == active_key),
                builtin_themes()[0],
            )
        self._render_saved_themes()
        self._sync_button_selection()

    def _render_saved_themes(self) -> None:
        while self._saved_layout.count():
            item = self._saved_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._theme_btns.clear()
        self._saved_btns.clear()

        for theme in builtin_themes():
            desc = _THEME_DESCRIPTIONS.get(theme.key, "builtin theme")
            btn = _ThemeBtn(theme, desc, False)
            btn.clicked.connect(lambda _, t=theme: self._select_local_theme(t))
            self._theme_btns[theme.key] = btn
            self._saved_layout.addWidget(btn)

        for saved in self._saved_themes:
            subtitle = f"by {saved.author}"
            btn = _ThemeBtn(
                saved.theme,
                subtitle,
                False,
                removable=True,
                remove_callback=lambda slug=saved.slug: self._remove_saved_theme(slug),
            )
            btn.clicked.connect(lambda _, slug=saved.slug: self._select_saved_theme(slug))
            self._saved_btns[saved.slug] = btn
            self._saved_layout.addWidget(btn)

        self._saved_layout.addStretch(1)

    def _import_theme_from_input(self) -> None:
        raw = self._import_input.text().strip()
        if not raw:
            self._status_lbl.hide()
            return
        try:
            normalize_vscode_theme_slug(raw)
        except ValueError as exc:
            self._status_lbl.setText(f"could not import theme: {exc}")
            self._status_lbl.show()
            return

        # Prevent duplicate concurrent imports
        if hasattr(self, "_import_worker") and self._import_worker is not None:
            if self._import_worker.isRunning():
                return

        self._import_btn.setEnabled(False)
        self._import_input.setEnabled(False)
        self._status_lbl.setText("importing\u2026")
        self._status_lbl.show()

        self._import_worker = ThemeImportWorker(raw, parent=self)
        self._import_worker.succeeded.connect(self._on_import_succeeded)
        self._import_worker.failed.connect(self._on_import_failed)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.start()

    def _on_import_succeeded(self, snapshot: object) -> None:
        """Handle a successfully fetched theme snapshot."""
        slug = snapshot.slug
        theme = theme_from_import_palette(snapshot.palette, slug)
        saved = save_imported_theme(theme, slug, snapshot.author)
        active_theme = apply_saved_imported_theme(saved.slug)
        self._sync_from_settings()
        self._import_input.clear()
        self._status_lbl.hide()
        self.accent_changed.emit(active_theme.accent)

    def _on_import_failed(self, message: str) -> None:
        """Handle a theme import failure."""
        self._status_lbl.setText(f"could not import theme: {message}")
        self._status_lbl.show()

    def _on_import_finished(self) -> None:
        """Re-enable UI controls after the import worker completes."""
        self._import_btn.setEnabled(True)
        self._import_input.setEnabled(True)
        self._import_worker = None

    def _select_local_theme(self, theme: Theme) -> None:
        self._selected_theme = theme
        self._selected_saved_slug = ""
        apply_builtin_theme(theme)
        self._sync_button_selection()
        self._status_lbl.hide()
        self.accent_changed.emit(theme.accent)

    def _select_saved_theme(self, slug: str) -> None:
        try:
            theme = apply_saved_imported_theme(slug)
        except (KeyError, TypeError, ValueError) as exc:
            self._status_lbl.setText(f"could not apply theme: {exc}")
            self._status_lbl.show()
            return
        self._selected_theme = None
        self._selected_saved_slug = slug
        self._sync_button_selection()
        self._status_lbl.hide()
        self.accent_changed.emit(theme.accent)

    def _remove_saved_theme(self, slug: str) -> None:
        was_active = self._selected_saved_slug == slug
        removed = remove_saved_imported_theme(slug)
        if not removed:
            self._status_lbl.setText("theme was already removed")
            self._status_lbl.show()
            return
        self._sync_from_settings()
        if was_active:
            current = next(
                (theme for theme in builtin_themes() if theme.key == "crucible"),
                builtin_themes()[0],
            )
            self._status_lbl.hide()
            self.accent_changed.emit(current.accent)
        else:
            self._status_lbl.hide()

    def _sync_button_selection(self) -> None:
        local_key = self._selected_theme.key if self._selected_theme is not None else ""
        for key, btn in self._theme_btns.items():
            btn.set_selected(key == local_key)
        for slug, btn in self._saved_btns.items():
            btn.set_selected(slug == self._selected_saved_slug)
