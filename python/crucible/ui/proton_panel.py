from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLayout,
    QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from crucible.core.proton_manager import ProtonManager
from crucible.ui import styles
from crucible.ui.proton_download import DownloadMixin
from crucible.ui.proton_version_row import VersionRow
from crucible.ui.proton_workers import _FetchWorker
from crucible.ui.styles import get_text_colors, line_accent, panel_fill

PANEL_W = 288

class ProtonPanel(DownloadMixin, QWidget):
    def __init__(self, proton_manager: ProtonManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProtonPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._proton_manager = proton_manager
        self._download_in_progress = False
        self._worker = None
        self._fetch_worker = None
        self._installed_rows: list[VersionRow] = []
        self._available_rows: list[VersionRow] = []

        self._apply_style()
        self._build_ui()
        self.refresh_colors()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"#ProtonPanel {{ background: {panel_fill()}; border: none; }}")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._head = QWidget()
        head_layout = QHBoxLayout(self._head)
        head_layout.setContentsMargins(14, 12, 14, 12)
        head_layout.setSpacing(0)
        self._head_title = QLabel("proton")
        self._head_meta = QLabel("installed + available")
        head_layout.addWidget(self._head_title)
        head_layout.addStretch(1)
        head_layout.addWidget(self._head_meta)
        root.addWidget(self._head)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(self._scroll.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply_scroll_style()

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(10, 10, 10, 10)
        vl.setSpacing(0)

        self._installed_group = QWidget()
        self._installed_group.setStyleSheet("background: transparent;")
        inst_group_layout = QVBoxLayout(self._installed_group)
        inst_group_layout.setContentsMargins(0, 0, 0, 8)
        inst_group_layout.setSpacing(0)
        self._inst_btn = QLabel("installed")
        inst_group_layout.addWidget(self._inst_btn)
        self._installed_widget = QWidget()
        self._installed_widget.setStyleSheet("background: transparent;")
        self._installed_vl = QVBoxLayout(self._installed_widget)
        self._installed_vl.setContentsMargins(0, 0, 0, 0)
        self._installed_vl.setSpacing(0)
        inst_group_layout.addWidget(self._installed_widget)
        vl.addWidget(self._installed_group)

        self._section_divider = QLabel()
        self._section_divider.setFixedHeight(1)
        vl.addWidget(self._section_divider)

        self._available_group = QWidget()
        self._available_group.setStyleSheet("background: transparent;")
        avail_group_layout = QVBoxLayout(self._available_group)
        avail_group_layout.setContentsMargins(0, 0, 0, 0)
        avail_group_layout.setSpacing(0)
        self._avail_btn = QLabel("available")
        avail_group_layout.addWidget(self._avail_btn)
        self._available_widget = QWidget()
        self._available_widget.setStyleSheet("background: transparent;")
        self._available_vl = QVBoxLayout(self._available_widget)
        self._available_vl.setContentsMargins(0, 0, 0, 0)
        self._available_vl.setSpacing(0)
        avail_group_layout.addWidget(self._available_widget)
        vl.addWidget(self._available_group)
        vl.addStretch()

        self._scroll.setWidget(inner)
        root.addWidget(self._scroll, 1)

        self._status_lbl = QLabel()
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setFixedHeight(20)
        self._status_lbl.hide()
        root.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(styles.progress_bar())
        self._progress.hide()
        root.addWidget(self._progress)

        self._action_bar = self._build_action_bar()
        root.addWidget(self._action_bar)

        self._refresh_sep_styles()
        self._style_status()

    def _apply_scroll_style(self) -> None:
        a = line_accent()
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{ background: transparent; width: 2px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {a}; min-height: 20px; border: none; }}"
            "QScrollBar::add-line:vertical,"
            "QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
            f"QScrollBar:horizontal {{ background: transparent; height: 2px; margin: 0; }}"
            f"QScrollBar::handle:horizontal {{ background: {a}; min-width: 20px; border: none; }}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
        )
        self._scroll.viewport().setAutoFillBackground(False)

    def _refresh_sep_styles(self) -> None:
        self._section_divider.setStyleSheet(f"background: {line_accent()};")

    def _style_collapse_btn(self, btn: QLabel) -> None:
        dim = get_text_colors()['text_dim']
        btn.setStyleSheet(
            f"color: {dim}; background: transparent; border: none;"
            f" font-family: 'Courier New', monospace; font-size: 8pt;"
            f" padding: 8px 8px 6px 8px; text-transform: uppercase;"
        )

    def _style_status(self) -> None:
        dim = get_text_colors()['text_dim']
        self._status_lbl.setStyleSheet(
            f"color: {dim}; font-family: 'Courier New', monospace;"
            f" font-size: 9pt; background: transparent;"
        )

    def _dim_label(self, text: str) -> QLabel:
        dim = get_text_colors()['text_dim']
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {dim}; font-family: 'Courier New', monospace;"
            f" font-size: 9pt; background: transparent; padding: 2px 8px;"
        )
        return lbl

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _uncheck_others(self, rows: list[VersionRow], keep: VersionRow | None) -> None:
        for r in rows:
            if r is not keep and r.isChecked():
                r.blockSignals(True)
                r.setChecked(False)
                r.blockSignals(False)
                r.update()

    def _selected_installed(self) -> VersionRow | None:
        return next((r for r in self._installed_rows if r.isChecked()), None)

    def _selected_available(self) -> VersionRow | None:
        return next((r for r in self._available_rows if r.isChecked()), None)

    def _update_action_bar_state(self) -> None:
        ins = self._selected_installed()
        avail = self._selected_available()
        self._remove_btn.setEnabled(bool(ins) and not self._download_in_progress)
        self._install_btn.setEnabled(bool(avail) and not self._download_in_progress)

    def open(self) -> None:
        """Call when the panel becomes visible to initialise data."""
        self._refresh_installed()
        self._start_fetch()

    def refresh_colors(self) -> None:
        """Re-apply all styles and row colors after a theme change."""
        self._apply_style()
        self._head.setStyleSheet(f"background: rgba(255,255,255,0.01); border-bottom: 1px solid {line_accent()};")
        self._head_title.setStyleSheet(f"color: {line_accent()}; font-family: 'Courier New', monospace; font-size: 10pt; font-weight: 700; background: transparent;")
        self._head_meta.setStyleSheet(f"color: {get_text_colors()['text_dim']}; font-family: 'Courier New', monospace; font-size: 9pt; background: transparent;")
        self._refresh_sep_styles()
        self._style_action_bar()
        self._style_status()
        self._apply_scroll_style()
        self._style_collapse_btn(self._inst_btn)
        self._style_collapse_btn(self._avail_btn)
        self._progress.setStyleSheet(styles.progress_bar())
        for row in self._installed_rows + self._available_rows:
            row.update()

    def _refresh_installed(self) -> None:
        self._proton_manager.scan_installed()
        names = self._proton_manager.get_installed_names()
        self._clear_layout(self._installed_vl)
        self._installed_rows.clear()
        if names:
            for name in names:
                row = VersionRow(name)
                row.toggled.connect(
                    lambda checked, r=row: self._on_installed_toggled(r, checked)
                )
                self._installed_vl.addWidget(row)
                self._installed_rows.append(row)
        else:
            self._installed_vl.addWidget(self._dim_label("none installed"))
        self._update_action_bar_state()

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
                row.toggled.connect(
                    lambda checked, r=row: self._on_available_toggled(r, checked)
                )
                self._available_vl.addWidget(row)
                self._available_rows.append(row)
        else:
            self._available_vl.addWidget(self._dim_label("none found"))
        self._update_action_bar_state()

    def _on_installed_toggled(self, row: VersionRow, checked: bool) -> None:
        if checked:
            self._uncheck_others(self._installed_rows, row)
            self._uncheck_others(self._available_rows, None)
        self._update_action_bar_state()

    def _on_available_toggled(self, row: VersionRow, checked: bool) -> None:
        if checked:
            self._uncheck_others(self._available_rows, row)
            self._uncheck_others(self._installed_rows, None)
        self._update_action_bar_state()

    def _on_remove(self) -> None:
        row = self._selected_installed()
        if not row:
            return
        if self._proton_manager.delete_version(row._name):
            self._refresh_installed()
