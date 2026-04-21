"""Minimal widget helpers — file dialogs for the web bridge."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PyQt6.QtWidgets import QFileDialog, QWidget


@contextmanager
def _clean_style(parent: QWidget | None) -> Iterator[None]:
    """Temporarily strip the app stylesheet so the native dialog is unthemed."""
    if parent is None:
        yield
        return
    window = parent.window()
    old = window.styleSheet()
    window.setStyleSheet("")
    try:
        yield
    finally:
        window.setStyleSheet(old)


def get_executable_path(parent: QWidget | None = None) -> str | None:
    """Open a file dialog to select an .exe file, returning the path or None."""
    with _clean_style(parent):
        path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Game Executable",
            str(Path.home()),
            "Executable files (*.exe);;All files (*)",
        )
    return path or None


def get_directory_path(
    parent: QWidget | None = None,
    title: str = "Select Directory",
    start_dir: str | None = None,
) -> str | None:
    """Open a file dialog to select a directory, returning the path or None."""
    with _clean_style(parent):
        path = QFileDialog.getExistingDirectory(
            parent,
            title,
            start_dir or str(Path.home()),
        )
    return path or None
