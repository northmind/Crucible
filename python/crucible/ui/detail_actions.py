from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from crucible.ui.detail_widgets import _ActionRow, _AdvRow, _DangerRow, _ToolRow


def build_tools_section(
    *,
    env_options: list[tuple[str, str, str, str]],
    env_checkboxes: dict[str, _AdvRow],
    on_winetricks_toggled: Callable[..., None],
) -> tuple[QWidget, _ToolRow]:
    """Build the tools section with environment toggle rows and a winetricks launcher row."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(0)

    for sec, label, env_var, _val_on in env_options:
        if sec != "tools":
            continue
        row = _AdvRow(label)
        env_checkboxes[env_var] = row
        layout.addWidget(row)

    winetricks_row = _ToolRow("Launch Winetricks")
    winetricks_row.setChecked(False)
    winetricks_row.clicked.connect(on_winetricks_toggled)
    layout.addWidget(winetricks_row)

    return widget, winetricks_row


def build_shortcut_section(
    *,
    has_shortcut: bool,
    on_shortcut_action: Callable[..., None],
    on_open_shortcuts_folder: Callable[..., None],
) -> QWidget:
    """Build the desktop shortcut section with create/remove and open-folder rows."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(0)

    action_label = "Remove Desktop Shortcut" if has_shortcut else "Create Desktop Shortcut"
    action_row = _ActionRow(action_label)
    action_row.clicked.connect(on_shortcut_action)
    layout.addWidget(action_row)

    folder_row = _ActionRow("Open Shortcuts Folder")
    folder_row.clicked.connect(on_open_shortcuts_folder)
    layout.addWidget(folder_row)

    return widget


def build_danger_section(
    *,
    on_danger_row: Callable[[str, Callable[..., None]], None],
    actions: list[tuple[str, Callable[..., None]]],
) -> QWidget:
    """Build the danger zone section with destructive action rows."""
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(0)

    for label, action in actions:
        row = _DangerRow(label)
        row.clicked.connect(lambda _=False, lbl=label, act=action: on_danger_row(lbl, act))
        layout.addWidget(row)

    return widget
