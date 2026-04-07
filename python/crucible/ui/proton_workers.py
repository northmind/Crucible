from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from crucible.core.proton_manager import ProtonManager
from crucible.core.workers import register_worker


class _FetchWorker(QThread):
    result = pyqtSignal(list)

    def __init__(self, proton_manager: ProtonManager) -> None:
        super().__init__()
        self._manager = proton_manager
        register_worker(self)

    def run(self) -> None:
        self.result.emit([v['tag'] for v in self._manager.fetch_available()])


class _DownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    result   = pyqtSignal(str)

    def __init__(self, proton_manager: ProtonManager, version: str) -> None:
        super().__init__()
        self._manager = proton_manager
        self._version = version
        self._cancel_event = threading.Event()
        register_worker(self)

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        success = self._manager.download_and_install(
            self._version,
            progress_callback=self.progress.emit,
            cancel_event=self._cancel_event,
        )
        self.result.emit("cancelled" if self._cancel_event.is_set() else ("success" if success else "failed"))
