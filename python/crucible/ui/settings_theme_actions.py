from __future__ import annotations

from crucible.ui.theme_button import _ThemeBtn
from crucible.ui.theme_importer import import_vscode_theme_snapshot, normalize_vscode_theme_slug
from crucible.ui.theme_system import (
    Theme,
    apply_builtin_theme,
    apply_saved_imported_theme,
    builtin_themes,
    get_active_saved_theme_slug,
    list_saved_imported_themes,
    remove_saved_imported_theme,
    save_imported_theme,
    theme_from_import_palette,
)

_THEME_DESCRIPTIONS = {
    "crucible": "by Nakama",
}


class SettingsThemeMixin:
    """Theme selection, import, and removal logic for SettingsPanel."""

    def _sync_from_settings(self) -> None:
        self._saved_themes = list_saved_imported_themes()
        self._selected_saved_slug = get_active_saved_theme_slug()
        if self._selected_saved_slug:
            self._selected_theme = None
        else:
            self._selected_theme = next(
                (theme for theme in builtin_themes() if theme.key == "crucible"),
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

        crucible = next(theme for theme in builtin_themes() if theme.key == "crucible")
        crucible_btn = _ThemeBtn(crucible, _THEME_DESCRIPTIONS["crucible"], False)
        crucible_btn.clicked.connect(lambda _, theme=crucible: self._select_local_theme(theme))
        self._theme_btns[crucible.key] = crucible_btn
        self._saved_layout.addWidget(crucible_btn)

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
            slug = normalize_vscode_theme_slug(raw)
            remote = import_vscode_theme_snapshot(slug)
            theme = theme_from_import_palette(remote.palette, remote.slug)
        except (OSError, ValueError, KeyError) as exc:
            self._status_lbl.setText(f"could not import theme: {exc}")
            self._status_lbl.show()
            return

        saved = save_imported_theme(theme, slug, remote.author)
        active_theme = apply_saved_imported_theme(saved.slug)
        self._sync_from_settings()
        self._import_input.clear()
        self._status_lbl.hide()
        self.accent_changed.emit(active_theme.accent)

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
