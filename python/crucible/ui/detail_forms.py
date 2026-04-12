from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QFrame,
    QVBoxLayout,
    QWidget,
)

from crucible.core.types import GameDict
from crucible.ui import styles
from crucible.ui.detail_widgets import _AdvRow, _ProtonRow
from crucible.ui.styles import get_text_colors
from crucible.ui.theme_system import get_selection_colors
from crucible.ui.tokens import FONT_BASE, FONT_MONO, FONT_XS
from crucible.ui.widgets import folder_icon


class _ConfigRow(QWidget):
    activated = pyqtSignal(object)

    def __init__(self, key: str, label: str, *, on_browse: Callable[[str, QLineEdit], None] | None = None, browse_key: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._browse_key = browse_key
        self._on_browse = on_browse
        self._hovered = False
        self._active = False
        self.setObjectName('ConfigRow')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(3)

        self._label = QLabel(label)
        self._label.setFixedWidth(48)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label)

        self._stack = QStackedWidget()
        self._stack.setFrameShape(QFrame.Shape.NoFrame)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setFixedHeight(28)
        self._stack.setStyleSheet("background: transparent; border: none;")

        self._display = QLabel()
        self._display.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._display.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._display.setFixedHeight(28)
        self._display.setStyleSheet("background: transparent;")
        self._display.setContentsMargins(0, 0, 0, 0)
        self._display.setMinimumWidth(0)
        self._display.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        self._edit = QLineEdit()
        self._edit.setFixedHeight(28)
        self._edit.editingFinished.connect(self.deactivate)
        self._edit.textChanged.connect(self._sync_display)

        self._stack.addWidget(self._display)
        self._stack.addWidget(self._edit)
        layout.addWidget(self._stack, 1)

        if browse_key:
            self._browse_btn = QPushButton()
            self._browse_btn.setFlat(True)
            self._browse_btn.setFixedSize(20, 20)
            self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._browse_btn.setAccessibleName("Browse")
            self._browse_btn.clicked.connect(self._browse)
            layout.addWidget(self._browse_btn)
        else:
            self._browse_btn = None
            spacer = QLabel("")
            spacer.setFixedWidth(20)
            layout.addWidget(spacer)

        self._refresh_style()

    @property
    def edit(self) -> QLineEdit:
        return self._edit

    def setText(self, text: str) -> None:
        self._edit.setText(text)
        self._sync_display(text)

    def text(self) -> str:
        return self._edit.text()

    def activate(self) -> None:
        if self._active:
            return
        self._active = True
        self._stack.setCurrentWidget(self._edit)
        self._edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self.activated.emit(self)
        self._refresh_style()

    def deactivate(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stack.setCurrentWidget(self._display)
        self._refresh_style()

    def set_active(self, active: bool) -> None:
        if active:
            self.activate()
        else:
            self.deactivate()

    def _sync_display(self, text: str) -> None:
        shown = text or ""
        self._display.setText(shown)
        self._display.setToolTip(shown if shown else "")

    def _browse(self) -> None:
        if self._on_browse and self._browse_key:
            self._on_browse(self._browse_key, self._edit)
        self.activate()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._browse_btn and self._browse_btn.geometry().contains(event.position().toPoint()):
            super().mousePressEvent(event)
            return
        self.activate()
        super().mousePressEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self._refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event: QEnterEvent) -> None:
        self._hovered = False
        self._refresh_style()
        super().leaveEvent(event)

    def _refresh_style(self) -> None:
        text = get_text_colors()
        sel = get_selection_colors()

        row_bg = sel.hover_bg if self._hovered else 'transparent'
        self.setStyleSheet(
            f"QWidget#ConfigRow {{ background: {row_bg}; border: none; border-radius: 0px; }}"
        )
        self._label.setStyleSheet(
            f"color: {text.text_dim}; background: transparent;"
            f" font-family: {FONT_MONO}; font-size: {FONT_XS}pt; letter-spacing: 0.18em; text-transform: uppercase;"
        )
        self._display.setStyleSheet(
            f"color: {text.text}; background: transparent; border: none; padding: 0;"
            f" font-family: {FONT_MONO}; font-size: {FONT_BASE}pt;"
        )
        edit_bg = 'transparent'
        self._edit.setStyleSheet(
            f"color: {text.text}; background: {edit_bg}; border: none; padding: 2px 0; outline: none; selection-background-color: {sel.text_selection_bg}; selection-color: {sel.selection_text};"
            f" font-family: {FONT_MONO}; font-size: {FONT_BASE}pt;"
        )
        if self._browse_btn:
            self._browse_btn.setIcon(folder_icon(text.text_dim))
            self._browse_btn.setIconSize(QSize(12, 12))
            self._browse_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; padding: 0; color: {text.text_dim}; }}"
                f"QPushButton:hover {{ color: {sel.nav_accent}; background: transparent; }}"
            )


class _ConfigSection(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._rows: list[_ConfigRow] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def add_row(self, row: _ConfigRow) -> None:
        row.activated.connect(self._on_row_activated)
        self._rows.append(row)
        self._layout.addWidget(row)

    def _on_row_activated(self, active_row: _ConfigRow) -> None:
        for row in self._rows:
            if row is not active_row:
                row.deactivate()


def build_config_section(*, on_browse: Callable[[str, QLineEdit], None], env_options: list[tuple[str, str, str, str]], env_checkboxes: dict[str, _AdvRow]) -> tuple[QWidget, dict[str, QLineEdit], list[tuple[str, QWidget]]]:
    """Build the game config form section with name/exe/dir/prefix/args/env/dlls/wrap rows."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    rows = _ConfigSection()
    edits = {}

    def add(key: str, label: str, browse_key: str | None = None) -> None:
        row = _ConfigRow(key, label, on_browse=on_browse, browse_key=browse_key)
        edits[key] = row.edit
        rows.add_row(row)

    add('name', 'NAME')
    add('exe', 'EXE', 'EXE')
    add('dir', 'DIR', 'DIR')
    add('prefix', 'PFX', 'PFX')
    add('args', 'ARGS')
    add('env', 'ENV')
    add('dlls', 'DLLS')
    add('wrap', 'WRAP')
    layout.addWidget(rows)

    extra_sections: list[tuple[str, QWidget]] = []
    sections = {}
    for sec, label, env_var, val_on in env_options:
        if sec == 'tools':
            continue
        sections.setdefault(sec, []).append((label, env_var, val_on))

    for sec_name, opts in sections.items():
        section_content = QWidget()
        section_content.setStyleSheet("background: transparent;")
        section_layout = QVBoxLayout(section_content)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(1)
        for label, env_var, _val_on in opts:
            row = _AdvRow(label)
            env_checkboxes[env_var] = row
            section_layout.addWidget(row)
        extra_sections.append((sec_name, section_content))

    return widget, edits, extra_sections


def build_launch_section(*, parent: QWidget, proton_manager: object, game: GameDict) -> tuple[QWidget, QButtonGroup]:
    """Build the Proton version selection section with radio rows."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)

    proton_group = QButtonGroup(parent)
    proton_group.setExclusive(True)
    versions = proton_manager.get_installed_names()
    current = game.get('proton_version', '')
    if versions:
        for version in versions:
            row = _ProtonRow(version)
            proton_group.addButton(row)
            row.setChecked(version == current)
            layout.addWidget(row)
    else:
        no_versions = QLabel("no proton installed")
        no_versions.setContentsMargins(8, 2, 8, 2)
        no_versions.setStyleSheet(styles.mono_label())
        layout.addWidget(no_versions)

    return widget, proton_group
