from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QResizeEvent, QHideEvent
from PyQt6.QtWidgets import (
    QLabel, QLayout, QScrollArea, QVBoxLayout, QWidget,
)

from crucible.core.proton_manager import ProtonManager
from crucible.ui import styles
from crucible.ui.panel_helpers import build_collapsible_section, _SectionHeaderButton
from crucible.ui.proton_download import DownloadMixin
from crucible.ui.proton_toast import _ProtonToast
from crucible.ui.proton_version_row import VersionRow
from crucible.ui.proton_workers import _FetchWorker
from crucible.ui.styles import get_accent, panel_fill
from crucible.ui.tokens import PANEL_WIDTH, SPACE_SM, SPACE_MD, SPACE_XL
from crucible.ui.widgets import init_styled, make_scroll_page

PANEL_W = PANEL_WIDTH


class ProtonPanel(DownloadMixin, QWidget):

    def __init__(self, proton_manager: ProtonManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        init_styled(self, "ProtonPanel")

        self._proton_manager = proton_manager
        self._download_in_progress = False
        self._worker = None
        self._fetch_worker = None
        self._installed_rows: list[VersionRow] = []
        self._available_rows: list[VersionRow] = []
        self._section_headers: dict[str, _SectionHeaderButton] = {}

        self._apply_style()
        self._build_ui()
        self.refresh_colors()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"#ProtonPanel {{ background: {panel_fill()}; border: none; }}")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Scroll area with accent scrollbar --------------------------
        self._scroll = make_scroll_page(
            margins=(0, SPACE_MD, 0, SPACE_XL),
            accent=get_accent(),
        )
        vl = self._scroll.widget().layout()

        # --- Installed section (collapsible) ----------------------------
        self._installed_widget = QWidget()
        self._installed_widget.setStyleSheet("background: transparent;")
        self._installed_vl = QVBoxLayout(self._installed_widget)
        self._installed_vl.setContentsMargins(0, 0, 0, 0)
        self._installed_vl.setSpacing(0)

        inst_section, inst_header = build_collapsible_section(
            "Installed", self._installed_widget, expanded=False,
        )
        self._section_headers["installed"] = inst_header
        vl.addSpacing(SPACE_SM)
        vl.addWidget(inst_section)

        # --- Available section (collapsible) ----------------------------
        self._available_widget = QWidget()
        self._available_widget.setStyleSheet("background: transparent;")
        self._available_vl = QVBoxLayout(self._available_widget)
        self._available_vl.setContentsMargins(0, 0, 0, 0)
        self._available_vl.setSpacing(0)

        avail_section, avail_header = build_collapsible_section(
            "Available", self._available_widget, expanded=False,
        )
        self._section_headers["available"] = avail_header
        vl.addSpacing(SPACE_SM)
        vl.addWidget(avail_section)
        vl.addStretch()

        root.addWidget(self._scroll, 1)

        # --- Toast overlay (slides up from bottom on demand) ------------
        self._toast = _ProtonToast(self, on_dismiss=self._unhighlight_all)

    def _apply_scroll_style(self) -> None:
        self._scroll.setStyleSheet(styles.scroll_area(accent=get_accent()))

    def _dim_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(styles.mono_label(padding="2px 8px"))
        return lbl

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _unhighlight_all(self) -> None:
        for r in self._installed_rows + self._available_rows:
            r.highlighted = False

    # ---- Lifecycle ------------------------------------------------------

    def open(self) -> None:
        """Call when the panel becomes visible to initialise data."""
        self._refresh_installed()
        self._start_fetch()

    def refresh_colors(self) -> None:
        """Re-apply all styles after a theme change."""
        self._apply_style()
        self._apply_scroll_style()
        self._toast.refresh_colors()
        for header in self._section_headers.values():
            header.update()
        for row in self._installed_rows + self._available_rows:
            row.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._toast.reposition(self.width(), self.height())

    def hideEvent(self, event: QHideEvent) -> None:
        if self._toast.isVisible():
            self._toast.dismiss()
        super().hideEvent(event)

    # ---- Section population ---------------------------------------------

    def _refresh_installed(self) -> None:
        self._proton_manager.scan_installed()
        names = self._proton_manager.get_installed_names()
        self._clear_layout(self._installed_vl)
        self._installed_rows.clear()
        if names:
            for name in names:
                row = VersionRow(name)
                row.clicked.connect(lambda _=None, r=row: self._on_installed_clicked(r))
                self._installed_vl.addWidget(row)
                self._installed_rows.append(row)
        else:
            self._installed_vl.addWidget(self._dim_label("none installed"))

    def _start_fetch(self) -> None:
        if self._fetch_worker and self._fetch_worker.isRunning():
            return
        self._clear_layout(self._available_vl)
        self._available_rows.clear()
        self._available_vl.addWidget(self._dim_label("fetching..."))
        self._fetch_worker = _FetchWorker(self._proton_manager)
        self._fetch_worker.result.connect(self._on_fetch_done)
        self._fetch_worker.start()

    def _on_fetch_done(self, versions: list[str]) -> None:
        self._clear_layout(self._available_vl)
        self._available_rows.clear()
        if versions:
            for v in versions:
                row = VersionRow(v)
                row.clicked.connect(lambda _=None, r=row: self._on_available_clicked(r))
                self._available_vl.addWidget(row)
                self._available_rows.append(row)
        else:
            self._available_vl.addWidget(self._dim_label("none found"))

    # ---- Row click handlers ---------------------------------------------

    def _on_installed_clicked(self, row: VersionRow) -> None:
        if self._download_in_progress:
            return
        self._unhighlight_all()
        row.highlighted = True
        name = row._name
        self._toast.prompt(f"remove {name}", lambda: self._do_remove(name))

    def _on_available_clicked(self, row: VersionRow) -> None:
        if self._download_in_progress:
            return
        self._unhighlight_all()
        row.highlighted = True
        name = row._name
        self._toast.prompt(f"install {name}", lambda: self._do_install(name))

    def _do_install(self, version: str) -> None:
        self._unhighlight_all()
        self._start_download(version)

    def _do_remove(self, name: str) -> None:
        self._unhighlight_all()
        if self._proton_manager.delete_version(name):
            self._refresh_installed()
            self._toast.show_status(f"> {name} removed.")
        else:
            self._toast.show_status(f"> failed to remove {name}.")
