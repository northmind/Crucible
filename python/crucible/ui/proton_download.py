from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCloseEvent

from crucible.ui.proton_workers import _DownloadWorker


class DownloadMixin:
    """Mixin handling proton download and cancel logic for ProtonPanel."""

    def _start_download(self, version: str) -> None:
        """Begin downloading and installing a Proton version."""
        if self._download_in_progress:
            return
        self._download_in_progress = True
        self._toast.show_progress(f"> {version}", self._on_cancel)
        self._worker = _DownloadWorker(self._proton_manager, version)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._on_download_done)
        self._worker.start()

    def _on_cancel(self) -> None:
        if not self._worker or not self._worker.isRunning():
            return
        self._toast.disable_cancel()
        self._toast.set_message("> cancelling...")
        self._worker.cancel()

    def _on_progress(self, percent: int, _msg: str) -> None:
        self._toast.set_progress(percent)
        if percent >= 50:
            self._toast.set_message("> extracting...")

    def _on_download_done(self, outcome: str) -> None:
        self._download_in_progress = False
        if outcome == "success":
            msg, delay = "> done.", 1500
        elif outcome == "cancelled":
            msg, delay = "> cancelled.", 600
        else:
            msg, delay = "> failed.", 1500
        self._toast.show_status(msg, delay)
        QTimer.singleShot(delay + 300, self._reset_after_download)

    def _reset_after_download(self) -> None:
        self._worker = None
        self._refresh_installed()
        self._start_fetch()

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
