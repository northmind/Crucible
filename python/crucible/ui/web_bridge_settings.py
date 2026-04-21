"""Web bridge settings & runners mixin — proton management and app settings.

Mixed into WebBridge by web_bridge.py.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSlot

from crucible.ui import app_settings

if TYPE_CHECKING:
    from crucible.core.managers import GameManager
    from crucible.core.proton_manager import ProtonManager

class WebBridgeSettingsMixin:
    """Mixin providing runner management and settings slots."""

    _gm: GameManager
    _pm: ProtonManager

    # --- Proton / Wine Runners ---

    def ensureDefaultRunner(self) -> str:
        """Persist the newest installed runner when no valid default is set."""
        names = self._pm.get_installed_names()
        gc = self._gm.global_config
        current = str(gc.get("proton_version") or "")
        if current and current in names:
            return current
        if not names:
            return current
        default_runner = names[0]
        gc.set("proton_version", default_runner)
        return default_runner

    @pyqtSlot(str, result="QVariant")
    def getInstalledRunnersForSource(self, source: str) -> list[dict]:
        self._pm.scan_installed()
        self.ensureDefaultRunner()
        return [r for r in self._pm.installed if r.get('source') == source]

    @pyqtSlot(result="QVariant")
    def getRunnerNames(self) -> list[str]:
        self._pm.scan_installed()
        self.ensureDefaultRunner()
        return self._pm.get_installed_names()

    @pyqtSlot(str, result="QVariant")
    def fetchReleasesForSource(self, source: str) -> list[dict]:
        return self._pm.fetch_releases(source=source)

    @pyqtSlot(str, str)
    def downloadRunnerFromSource(self, tag: str, source: str) -> None:
        self._downloadRunnerImpl(tag, source)

    def _downloadRunnerImpl(self, tag: str, source: str) -> None:
        def _run() -> None:
            def _progress(pct: int, msg: str) -> None:
                self.downloadProgress.emit(  # type: ignore[attr-defined]
                    {"tag": tag, "percent": pct, "message": msg},
                )
            ok = self._pm.download_and_install(
                tag, progress_callback=_progress, source=source,
            )
            if ok:
                self.ensureDefaultRunner()
                self.toastRequested.emit(f"Installed {tag}", "success")  # type: ignore[attr-defined]
                self.protonChanged.emit()  # type: ignore[attr-defined]
            else:
                self.toastRequested.emit(f"Failed to install {tag}", "error")  # type: ignore[attr-defined]
        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot(str, result=bool)
    def deleteRunner(self, tag: str) -> bool:
        ok = self._pm.delete_version(tag)
        if ok:
            self.ensureDefaultRunner()
            self.protonChanged.emit()  # type: ignore[attr-defined]
        return ok

    # --- Settings ---

    @pyqtSlot(result="QVariant")
    def getSettings(self) -> dict:
        return {
            "minimize_to_tray": app_settings.minimize_to_tray(),
            "restore_geometry": app_settings.restore_geometry(),
            "sidebar_collapsed": app_settings.sidebar_collapsed(),
            "auto_update_umu": app_settings.auto_update_umu(),
            "custom_proton_dir": app_settings.custom_proton_dir(),
            "log_level": app_settings.log_level(),
            "font_family": app_settings.font_family(),
        }

    @pyqtSlot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        setters = {
            "minimize_to_tray": app_settings.set_minimize_to_tray,
            "restore_geometry": app_settings.set_restore_geometry,
            "sidebar_collapsed": app_settings.set_sidebar_collapsed,
            "auto_update_umu": app_settings.set_auto_update_umu,
            "custom_proton_dir": app_settings.set_custom_proton_dir,
            "log_level": app_settings.set_log_level,
            "font_family": app_settings.set_font_family,
        }
        setter = setters.get(key)
        if setter:
            setter(value)
            if key == "log_level":
                from crucible.core.logger import apply_log_level
                apply_log_level(value)
            elif key == "custom_proton_dir":
                extra_dirs = [Path(value)] if str(value).strip() else []
                self._pm.set_search_dirs(extra_dirs)
                self._pm.scan_installed()
                self.ensureDefaultRunner()
                self.protonChanged.emit()  # type: ignore[attr-defined]
            elif key == "sidebar_collapsed":
                return
            self.toastRequested.emit(f"Setting '{key}' updated", "success")  # type: ignore[attr-defined]

    # --- Global Config ---

    @pyqtSlot(result="QVariant")
    def getGlobalConfig(self) -> dict:
        d = self._gm.global_config.as_dict()
        # Flatten gamescope_settings dict into gs_* keys for the settings UI.
        gs = d.get("gamescope_settings") or {}
        for k, v in gs.items():
            d["gs_" + k] = v
        # Expose proton_version under the UI-facing alias.
        d["default_runner"] = d.get("proton_version", "")
        d["force_grab_cursor"] = gs.get("enable_force_grab_cursor", False)
        return d

    # Keys the settings UI sends as flat ``gs_*`` that belong inside the
    # ``gamescope_settings`` dict in the actual config.
    _GS_NESTED_KEYS = frozenset({
        "gs_game_width", "gs_game_height", "gs_upscale_width",
        "gs_upscale_height", "gs_upscale_method", "gs_window_type",
        "gs_fps_limiter", "gs_fps_limiter_no_focus", "gs_additional_options",
    })

    @pyqtSlot(str, "QVariant")
    def setGlobalConfig(self, key: str, value) -> None:
        gc = self._gm.global_config
        if key == "default_runner":
            gc.set("proton_version", value)
        elif key == "force_grab_cursor":
            gs = dict(gc.get("gamescope_settings") or {})
            gs["enable_force_grab_cursor"] = value
            gc.set("gamescope_settings", gs)
        elif key in self._GS_NESTED_KEYS:
            gs = dict(gc.get("gamescope_settings") or {})
            gs[key[3:]] = value  # strip "gs_" prefix
            gc.set("gamescope_settings", gs)
        else:
            gc.set(key, value)

    @pyqtSlot(str, str, bool)
    def setGlobalEnvVar(self, key: str, value: str, enabled: bool) -> None:
        """Toggle an environment variable in global_config.env_vars."""
        env = dict(self._gm.global_config.get("env_vars") or {})
        if enabled:
            env[key] = value
        else:
            env.pop(key, None)
        self._gm.global_config.set("env_vars", env)
