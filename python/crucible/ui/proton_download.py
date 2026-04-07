from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from crucible.ui.proton_workers import _DownloadWorker
from crucible.ui.styles import get_text_colors, line_accent, line_accent_rgba


class DownloadMixin:
    """Mixin handling proton download, install, cancel, and action bar for ProtonPanel."""

    def _build_action_bar(self) -> QWidget:
        self._action_bar = QWidget()
        self._action_bar.setObjectName("ProtonActionBar")
        self._action_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._action_bar.setFixedHeight(34)

        hl = QHBoxLayout(self._action_bar)
        hl.setContentsMargins(16, 0, 12, 0)
        hl.setSpacing(6)
        hl.addStretch()

        self._cancel_btn = QPushButton("cancel")
        self._cancel_btn.setFlat(True)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._on_cancel)
        hl.addWidget(self._cancel_btn)

        self._remove_btn = QPushButton("remove")
        self._remove_btn.setFlat(True)
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        hl.addWidget(self._remove_btn)

        self._install_btn = QPushButton("install")
        self._install_btn.setFlat(True)
        self._install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_btn.setEnabled(False)
        self._install_btn.clicked.connect(self._on_install)
        hl.addWidget(self._install_btn)

        self._style_action_bar()
        return self._action_bar

    def _style_action_bar(self) -> None:
        self._action_bar.setStyleSheet(
            f"#ProtonActionBar {{ background: transparent;"
            f" border-top: 1px solid {line_accent()}; }}"
        )
        dim = get_text_colors()['text_dim']
        a = line_accent()
        btn_s = (
            f"QPushButton {{ color: {a}; background: transparent; border: none;"
            f" font-family: 'Courier New', monospace; font-size: 9pt; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {a}; background: {line_accent_rgba(10)}; }}"
            f"QPushButton:disabled {{ color: {dim}; }}"
        )
        for b in (self._remove_btn, self._install_btn, self._cancel_btn):
            b.setStyleSheet(btn_s)

    def _on_install(self) -> None:
        row = self._selected_available()
        if not row or self._download_in_progress:
            return
        version = row._name
        self._download_in_progress = True
        self._remove_btn.setEnabled(False)
        self._install_btn.setEnabled(False)
        self._remove_btn.hide()
        self._install_btn.hide()
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.show()
        self._set_status(f"> {version}")
        self._progress.setValue(0)
        self._progress.show()
        self._worker = _DownloadWorker(self._proton_manager, version)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._on_download_done)
        self._worker.start()

    def _on_cancel(self) -> None:
        if not self._worker or not self._worker.isRunning():
            return
        self._cancel_btn.setEnabled(False)
        self._set_status("> cancelling...")
        self._worker.cancel()

    def _on_progress(self, percent: int, _msg: str) -> None:
        self._progress.setValue(percent)
        if percent >= 50:
            self._set_status("> extracting...")

    def _on_download_done(self, outcome: str) -> None:
        self._download_in_progress = False
        if outcome == "success":
            self._set_status("> done.")
            delay = 1500
        elif outcome == "cancelled":
            self._set_status("> cancelled.")
            delay = 600
        else:
            self._set_status("> failed.")
            delay = 1500
        QTimer.singleShot(delay, self._reset_after_download)

    def _reset_after_download(self) -> None:
        self._progress.hide()
        self._status_lbl.hide()
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.hide()
        self._remove_btn.show()
        self._install_btn.show()
        self._worker = None
        self._refresh_installed()
        self._start_fetch()

    def _set_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        self._status_lbl.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel any running download and wait for workers to finish."""
        if self._download_in_progress and self._worker:
            self._on_cancel()
            self._worker.wait(5000)
        if self._fetch_worker:
            try:
                self._fetch_worker.result.disconnect(self._on_fetch_done)
            except TypeError:
                pass
            self._fetch_worker.wait(2000)
        super().closeEvent(event)
