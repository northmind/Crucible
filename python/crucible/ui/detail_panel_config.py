from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit

from crucible.core.paths import safe_name
from crucible.ui.detail_actions import build_danger_section, build_shortcut_section, build_tools_section
from crucible.ui.detail_forms import build_config_section, build_launch_section
from crucible.ui.detail_logs import build_logs_section
from crucible.ui.detail_perf import (
    build_gamescope_section,
    build_perf_section,
    build_scripts_section,
    build_security_section,
)
from crucible.ui.game_config import (
    _ENV_OPTIONS,
    collect_env_vars,
    custom_env_text,
    normalize_args,
    normalize_dll_overrides,
    normalize_env_text,
    populate_env_vars,
)
from crucible.ui.panel_helpers import build_collapsible_section
from crucible.ui.widgets import get_directory_path, get_executable_path


class ConfigMixin:
    """Mixin handling section building, form population, and auto-save for GameDetailPanel."""

    def _rebuild_view(self) -> None:
        previous_states = {
            name: header.is_expanded()
            for name, header in getattr(self, '_section_headers', {}).items()
        }
        self._clear_content()
        self._env_checkboxes = {}
        self._section_headers = {}
        self._wt_row = None
        self._proton_group = None
        self._perf_ctrl = {}
        self._gs_ctrl = {}
        self._scripts_ctrl = {}
        self._sec_ctrl = {}

        if not self._game:
            self._content_layout.addStretch()
            return

        config_widget, config_edits, extra_sections = build_config_section(
            on_browse=self._on_browse,
            env_options=_ENV_OPTIONS,
            env_checkboxes=self._env_checkboxes,
        )
        self._e_name = config_edits['name']
        self._e_exe = config_edits['exe']
        self._e_dir = config_edits['dir']
        self._e_prefix = config_edits['prefix']
        self._e_args = config_edits['args']
        self._e_dlls = config_edits['dlls']
        self._e_wrap = config_edits['wrap']
        self._e_env = config_edits['env']
        section, header = build_collapsible_section(
            self._section_title('game config'),
            config_widget,
            expanded=previous_states.get('game config', False),
        )
        self._section_headers['game config'] = header
        self._content_layout.addWidget(section)

        proton_widget, self._proton_group = build_launch_section(
            parent=self,
            proton_manager=self._proton_manager,
            game=self._game,
        )
        self._add_section('proton', proton_widget, expanded=previous_states.get('proton', False))

        extra_map = {name: widget for name, widget in extra_sections}
        for section_name in ('upscaling', 'compatibility', 'debug'):
            section_widget = extra_map.get(section_name)
            if section_widget is None:
                continue
            self._add_section(section_name, section_widget, expanded=previous_states.get(section_name, False))

        tools_widget, self._wt_row = build_tools_section(
            env_options=_ENV_OPTIONS,
            env_checkboxes=self._env_checkboxes,
            on_winetricks_toggled=self._on_winetricks_toggled,
        )
        self._add_section('tools', tools_widget, expanded=previous_states.get('tools', False))

        perf_w, self._perf_ctrl = build_perf_section(self._game)
        self._add_section('performance', perf_w, expanded=previous_states.get('performance', False))

        gs_w, self._gs_ctrl = build_gamescope_section(self._game)
        self._add_section('gamescope', gs_w, expanded=previous_states.get('gamescope', False))

        scripts_w, self._scripts_ctrl = build_scripts_section(self._game, self._on_browse)
        self._add_section('scripts', scripts_w, expanded=previous_states.get('scripts', False))

        sec_w, self._sec_ctrl = build_security_section(self._game)
        self._add_section('security', sec_w, expanded=previous_states.get('security', False))

        shortcut_widget = build_shortcut_section(
            has_shortcut=self._game_manager.has_game_shortcut(self._game.get('name', '')),
            on_shortcut_action=self._on_shortcut_action,
            on_open_shortcuts_folder=self._open_shortcuts_folder,
        )
        self._add_section('desktop shortcut', shortcut_widget, expanded=previous_states.get('desktop shortcut', False))

        logs_widget = build_logs_section(self._game)
        self._add_section('logs', logs_widget, expanded=previous_states.get('logs', False))

        danger_widget = build_danger_section(
            on_danger_row=self._on_danger_row,
            actions=[
                ('remove game data', self._do_delete_game),
                ('reset prefix', self._do_reset_prefix),
                ('clear logs', self._do_clear_logs),
                ('remove umu', self._do_remove_umu),
            ],
        )
        self._add_section('remove data', danger_widget, expanded=previous_states.get('remove data', False))
        self._content_layout.addStretch()

        self._loading = True
        self._e_name.setText(self._game.get('name', ''))
        self._e_exe.setText(self._game.get('exe_path', ''))
        self._e_dir.setText(self._game.get('install_dir', ''))
        self._e_prefix.setText(self._game.get('prefix_path', ''))
        self._e_args.setText(self._game.get('launch_args', ''))
        self._e_dlls.setText(self._game.get('custom_overrides', ''))
        self._e_wrap.setText(self._game.get('wrapper_command', ''))
        self._e_env.setText(custom_env_text(self._game.get('env_vars', {})))
        self._populate_env_vars(self._game.get('env_vars', {}))
        self._loading = False

        self._connect_save_signals()

    def _connect_save_signals(self) -> None:
        def queue_save():
            if not self._loading:
                self._save_timer.start()

        for edit in (self._e_name, self._e_exe, self._e_dir, self._e_prefix,
                     self._e_args, self._e_dlls, self._e_wrap, self._e_env):
            edit.textChanged.connect(queue_save)

        def normalize(edit, fn):
            def do_normalize():
                cleaned = fn(edit.text())
                if cleaned != edit.text():
                    edit.blockSignals(True)
                    edit.setText(cleaned)
                    edit.blockSignals(False)
                    queue_save()
            edit.editingFinished.connect(do_normalize)

        normalize(self._e_args, normalize_args)
        normalize(self._e_dlls, normalize_dll_overrides)
        normalize(self._e_wrap, normalize_args)
        normalize(self._e_env, normalize_env_text)

        for row in self._env_checkboxes.values():
            row.toggled.connect(queue_save)

        for button in self._proton_group.buttons():
            button.toggled.connect(queue_save)

        if self._wt_proc and self._wt_row is not None:
            self._wt_row.setChecked(True)

        # Performance / gamescope / scripts / security toggles + edits
        for toggle in (self._perf_ctrl["gamemode"], self._perf_ctrl["gamescope"],
                       self._gs_ctrl["grab_cursor"], self._sec_ctrl["fingerprint"]):
            toggle.toggled.connect(queue_save)
        for key in ("game_w", "game_h", "up_w", "up_h", "method", "window",
                     "fps", "fps_nofocus", "additional"):
            self._gs_ctrl[key].textChanged.connect(queue_save)
        for key in ("pre_script", "post_script"):
            self._scripts_ctrl[key].textChanged.connect(queue_save)

    def _on_browse(self, key: str, target: QLineEdit) -> None:
        if key == 'EXE':
            path = get_executable_path(self)
            if path:
                target.setText(path)
            return
        path = get_directory_path(self, start_dir=target.text().strip() or None)
        if path:
            target.setText(path)

    def _collect_env_vars(self) -> dict[str, str]:
        return collect_env_vars(self._env_checkboxes, self._e_env.text())

    def _populate_env_vars(self, env_vars: dict[str, str]) -> None:
        if not hasattr(self, '_env_checkboxes'):
            return
        populate_env_vars(
            env_vars,
            self._env_checkboxes,
            custom_env_edit=self._e_env if hasattr(self, '_e_env') else None,
        )

    def _auto_save(self) -> None:
        if not self._game or self._loading:
            return
        new_name = self._e_name.text().strip()
        new_exe = self._e_exe.text().strip()
        if not new_name or not new_exe:
            return

        checked = self._proton_group.checkedButton() if self._proton_group else None
        new_proton = checked.text() if checked else ''

        gs_settings = {
            "game_width": self._gs_ctrl["game_w"].text().strip(),
            "game_height": self._gs_ctrl["game_h"].text().strip(),
            "upscale_width": self._gs_ctrl["up_w"].text().strip(),
            "upscale_height": self._gs_ctrl["up_h"].text().strip(),
            "upscale_method": self._gs_ctrl["method"].text().strip(),
            "window_type": self._gs_ctrl["window"].text().strip(),
            "fps_limiter": self._gs_ctrl["fps"].text().strip(),
            "fps_limiter_no_focus": self._gs_ctrl["fps_nofocus"].text().strip(),
            "enable_force_grab_cursor": self._gs_ctrl["grab_cursor"].isChecked(),
            "additional_options": self._gs_ctrl["additional"].text().strip(),
        }

        self._game_manager.add_game(
            name=new_name,
            exe=new_exe,
            proton=new_proton,
            args=self._e_args.text().strip(),
            custom_overrides=normalize_dll_overrides(self._e_dlls.text()),
            install_dir=self._e_dir.text().strip(),
            env_vars=self._collect_env_vars(),
            prefix_path=self._e_prefix.text().strip(),
            wrapper_command=self._e_wrap.text().strip(),
            exe_match_mode=self._game.get('exe_match_mode', 'auto'),
            enable_gamemode=self._perf_ctrl["gamemode"].isChecked(),
            enable_gamescope=self._perf_ctrl["gamescope"].isChecked(),
            gamescope_settings=gs_settings,
            fingerprint_lock=self._sec_ctrl["fingerprint"].isChecked(),
            pre_launch_script=self._scripts_ctrl["pre_script"].text().strip(),
            post_launch_script=self._scripts_ctrl["post_script"].text().strip(),
        )

        old_name = self._game.get('name', '')
        if safe_name(old_name) != safe_name(new_name):
            old_file = self._game_manager.games_dir / f'{safe_name(old_name)}.json'
            if old_file.exists():
                old_file.unlink()
            self._game_manager.scan_games()

        self._game = {**self._game, 'name': new_name}
        self.game_updated.emit()
