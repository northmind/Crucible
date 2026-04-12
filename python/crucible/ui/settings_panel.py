from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crucible.ui.panel_helpers import TabBar
from crucible.ui.settings_theme_actions import SettingsThemeMixin
from crucible.ui.styles import line_accent, panel_fill
from crucible.ui import styles
from crucible.ui.theme_button import _ThemeBtn
from crucible.ui.tokens import FONT_BASE, FONT_MONO, FONT_XS, PANEL_WIDTH, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL
from crucible.ui.widgets import init_styled, make_divider, make_flat_button, make_scroll_page
from crucible.ui.theme_system import (
    SavedImportedTheme,
    migrate_legacy_remote_theme,
)

PANEL_W = PANEL_WIDTH
KOFI_URL = "https://ko-fi.com/nakama76442"


class SettingsPanel(SettingsThemeMixin, QWidget):
    accent_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        init_styled(self, "SettingsPanel")

        self._selected_theme = None
        self._selected_saved_slug = ""
        self._theme_btns: dict[str, _ThemeBtn] = {}
        self._saved_btns: dict[str, _ThemeBtn] = {}
        self._saved_themes: list[SavedImportedTheme] = []

        migrate_legacy_remote_theme()
        self._apply_style()
        self._build_ui()
        self._sync_from_settings()
        self.refresh_colors()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"#SettingsPanel {{ background: {panel_fill()}; border: none; }}")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tab_bar = TabBar(["themes", "general"], self, variant="panel")
        self._tab_bar.switched.connect(self._on_tab_switched)
        root.addWidget(self._tab_bar)

        self._tab_sep = QLabel()
        self._tab_sep.setFixedHeight(1)
        root.addWidget(self._tab_sep)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_themes_page())
        self._stack.addWidget(self._build_general_page())
        root.addWidget(self._stack, 1)

        self._refresh_sep_styles()

    def _build_themes_page(self) -> QWidget:
        scroll = make_scroll_page(
            margins=(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD),
        )
        layout = scroll.widget().layout()

        self._import_hdr = self._link_header("import from vscodethemes", "https://vscodethemes.com/")
        layout.addWidget(self._import_hdr)
        layout.addWidget(make_divider())
        layout.addSpacing(SPACE_MD)

        import_row = QHBoxLayout()
        import_row.setContentsMargins(0, 0, 0, 0)
        import_row.setSpacing(SPACE_SM)
        self._import_input = QLineEdit()
        self._import_input.setPlaceholderText("paste theme url here")
        self._import_input.returnPressed.connect(self._import_theme_from_input)
        self._style_input(self._import_input)
        import_row.addWidget(self._import_input, 1)

        self._import_btn = QPushButton("import")
        self._import_btn.clicked.connect(self._import_theme_from_input)
        self._style_nav_btn(self._import_btn, width=52, text_size=8)
        import_row.addWidget(self._import_btn)
        layout.addLayout(import_row)
        layout.addSpacing(SPACE_MD)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.hide()
        layout.addWidget(self._status_lbl)
        layout.addSpacing(SPACE_LG)

        self._saved_hdr = self._section_header("saved themes")
        layout.addWidget(self._saved_hdr)
        layout.addWidget(make_divider())
        layout.addSpacing(SPACE_MD)

        self._saved_container = QWidget()
        self._saved_container.setStyleSheet("background: transparent;")
        self._saved_layout = QVBoxLayout(self._saved_container)
        self._saved_layout.setContentsMargins(0, 0, 0, 0)
        self._saved_layout.setSpacing(SPACE_MD)
        layout.addWidget(self._saved_container)

        layout.addStretch()
        return scroll

    def _build_general_page(self) -> QWidget:
        scroll = make_scroll_page(
            margins=(SPACE_XL, 20, SPACE_XL, 20),
            spacing=SPACE_MD,
        )
        layout = scroll.widget().layout()

        placeholder = QLabel("more settings coming")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(styles.mono_label())
        layout.addWidget(placeholder)
        layout.addStretch()
        return scroll

    def _refresh_sep_styles(self) -> None:
        self._tab_sep.setStyleSheet(styles.divider())

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(styles.section_header())
        return lbl

    def _link_header(self, text: str, url: str) -> QLabel:
        lbl = QLabel(f'<a href="{url}">{text}</a>')
        lbl.setOpenExternalLinks(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        lbl.setStyleSheet(
            f"QLabel {{ color: {line_accent()}; font-family: {FONT_MONO}; font-size: {FONT_BASE}pt; background: transparent; }} QLabel a {{ color: {line_accent()}; text-decoration: none; }}"
        )
        return lbl

    def _style_nav_btn(self, btn: QPushButton, width: int = 18, text_size: int = 10) -> None:
        btn.setFixedSize(width, 18 if width == 18 else 22)
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(styles.flat_button(size=f"{text_size}pt"))

    def _style_input(self, widget: QLineEdit) -> None:
        widget.setStyleSheet(styles.text_input(size=f"{FONT_XS}pt"))
        widget.setCursorPosition(0)

    def _on_tab_switched(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def refresh_colors(self) -> None:
        """Re-apply all styles after a theme or accent change."""
        self._apply_style()
        self._tab_bar.refresh_colors()
        self._refresh_sep_styles()
        for btn in self._theme_btns.values():
            btn.update()
        for btn in self._saved_btns.values():
            btn.update()
        self._status_lbl.setStyleSheet(styles.mono_label(size=f"{FONT_XS}pt"))
        self._style_nav_btn(self._import_btn, width=52, text_size=FONT_XS)
        self._style_input(self._import_input)
        if hasattr(self, '_saved_hdr'):
            self._saved_hdr.setStyleSheet(styles.section_header())
        if hasattr(self, '_import_hdr'):
            a = line_accent()
            self._import_hdr.setStyleSheet(
                f"QLabel {{ color: {a}; font-family: {FONT_MONO}; font-size: {FONT_BASE}pt; background: transparent; }} QLabel a {{ color: {a}; text-decoration: none; }}"
            )
