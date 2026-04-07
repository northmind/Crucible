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
from crucible.ui.styles import get_text_colors, line_accent, panel_fill
from crucible.ui.theme_button import _ThemeBtn
from crucible.ui.theme_system import (
    SavedImportedTheme,
    get_selection_colors,
    migrate_legacy_remote_theme,
)

PANEL_W = 288
KOFI_URL = "https://ko-fi.com/nakama76442"


class SettingsPanel(SettingsThemeMixin, QWidget):
    accent_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self._import_hdr = self._link_header("import from vscodethemes", "https://vscodethemes.com/")
        layout.addWidget(self._import_hdr)
        layout.addWidget(self._divider())
        layout.addSpacing(8)

        import_row = QHBoxLayout()
        import_row.setContentsMargins(0, 0, 0, 0)
        import_row.setSpacing(6)
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
        layout.addSpacing(8)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.hide()
        layout.addWidget(self._status_lbl)
        layout.addSpacing(12)

        self._saved_hdr = self._section_header("saved themes")
        layout.addWidget(self._saved_hdr)
        layout.addWidget(self._divider())
        layout.addSpacing(8)

        self._saved_container = QWidget()
        self._saved_container.setStyleSheet("background: transparent;")
        self._saved_layout = QVBoxLayout(self._saved_container)
        self._saved_layout.setContentsMargins(0, 0, 0, 0)
        self._saved_layout.setSpacing(10)
        layout.addWidget(self._saved_container)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_general_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)

        placeholder = QLabel("more settings coming")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {get_text_colors()['text_dim']}; font-family: 'Courier New', monospace; font-size: 9pt;"
        )
        layout.addWidget(placeholder)
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _refresh_sep_styles(self) -> None:
        self._tab_sep.setStyleSheet(f"background: {line_accent()};")

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {line_accent()}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent;"
        )
        return lbl

    def _link_header(self, text: str, url: str) -> QLabel:
        lbl = QLabel(f'<a href="{url}">{text}</a>')
        lbl.setOpenExternalLinks(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        lbl.setStyleSheet(
            f"QLabel {{ color: {line_accent()}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent; }} QLabel a {{ color: {line_accent()}; text-decoration: none; }}"
        )
        return lbl

    def _divider(self) -> QLabel:
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {line_accent()};")
        return sep

    def _style_nav_btn(self, btn: QPushButton, width: int = 18, text_size: int = 10) -> None:
        btn.setFixedSize(width, 18 if width == 18 else 22)
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ color: {get_text_colors()['text_dim']}; background: transparent; border: none; font-family: 'Courier New', monospace; font-size: {text_size}pt; }}"
            f"QPushButton:hover {{ color: {line_accent()}; }}"
        )

    def _style_input(self, widget: QLineEdit) -> None:
        colors = get_text_colors()
        widget.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {colors['text']}; border: none; font-family: 'Courier New', monospace; font-size: 8.5pt; padding: 2px 0px; selection-background-color: {get_selection_colors()['text_selection_bg']}; selection-color: {get_selection_colors()['selection_text']}; }}"
            f"QLineEdit::placeholder {{ color: {colors['text_dim']}; }}"
        )
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
        colors = get_text_colors()
        self._status_lbl.setStyleSheet(
            f"color: {colors['text_dim']}; font-family: 'Courier New', monospace; font-size: 8pt;"
        )
        self._style_nav_btn(self._import_btn, width=52, text_size=8)
        self._style_input(self._import_input)
        if hasattr(self, '_saved_hdr'):
            self._saved_hdr.setStyleSheet(
                f"color: {line_accent()}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent;"
            )
        if hasattr(self, '_import_hdr'):
            self._import_hdr.setStyleSheet(
                f"QLabel {{ color: {line_accent()}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent; }} QLabel a {{ color: {line_accent()}; text-decoration: none; }}"
            )
