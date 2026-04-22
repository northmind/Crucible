"""Web bridge — exposes Crucible backend to QWebEngineView via QWebChannel.

Registered as ``bridge`` on the QWebChannel. All return types are native
Python (QVariant auto-conversion) — no JSON.
"""

from __future__ import annotations

import logging
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

from crucible.core.managers import GameManager
from crucible.core.proton_manager import ProtonManager
from crucible.core.types import GameDict
from crucible.core.paths import display_name_from_exe, find_game_root, Paths
from crucible.core.events import event_bus
from crucible.ui.artwork_manager import ArtworkManager
from crucible.ui.web_bridge_ui import WebBridgeUIMixin
from crucible.ui.web_bridge_settings import WebBridgeSettingsMixin

_log = logging.getLogger(__name__)


_GAME_FIELDS: dict[str, Any] = {
    "name": "", "exe_path": "", "install_dir": "", "proton_version": "",
    "proton_path": "", "launch_args": "", "custom_overrides": "",
    "env_vars": {}, "disabled_env_vars": [], "prefix_path": "", "fingerprint_lock": False,
    "wrapper_command": "", "enable_gamemode": False, "enable_mangohud": False,
    "enable_gamescope": False,
    "disabled_global_flags": [],
    "gamescope_settings": {}, "playtime_seconds": 0, "last_played": "",
    "game_file": "", "exe_match_mode": "auto",
}


def _game_to_dict(game: GameDict) -> dict[str, Any]:
    """Convert a GameDict to a plain dict for the web UI."""
    return {k: game.get(k, d) for k, d in _GAME_FIELDS.items()}


def _game_to_modal_dict(game_manager: GameManager, game: GameDict) -> dict[str, Any]:
    resolved = game_manager.global_config.resolve(game)
    data = _game_to_dict(resolved)
    data["_raw"] = _game_to_dict(game)
    data["_global"] = _game_to_dict(game_manager.global_config.as_dict())
    return data


def _write_game_updates(game_manager: GameManager, game_file: Path, updates: dict[str, Any]) -> None:
    data = game_manager._load_game_record(game_file)
    data.update(updates)
    game_manager._write_game_record(game_file, data)


class WebBridge(WebBridgeSettingsMixin, WebBridgeUIMixin, QObject):
    """Bridge singleton exposed to JS via QWebChannel as ``bridge``."""

    gamesChanged = pyqtSignal()
    protonChanged = pyqtSignal()
    downloadProgress = pyqtSignal("QVariant")
    toastRequested = pyqtSignal(str, str)
    themeColorsChanged = pyqtSignal()
    portraitUpdated = pyqtSignal(str)  # exe_path
    heroUpdated = pyqtSignal(str)     # exe_path
    artworkFetchFinished = pyqtSignal(str)
    gameRunningChanged = pyqtSignal(str, bool)

    def __init__(
        self,
        game_manager: GameManager,
        proton_manager: ProtonManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._gm = game_manager
        self._pm = proton_manager
        self._artwork = ArtworkManager()
        self._active_view = "library"
        self._modal_game_name = ""

        event_bus.library_refreshed.connect(self.gamesChanged.emit)
        event_bus.game_launched.connect(
            lambda name: self.gameRunningChanged.emit(name, True),
        )
        event_bus.game_exited.connect(
            lambda name: self.gameRunningChanged.emit(name, False),
        )
        self._artwork.portrait_ready.connect(self.portraitUpdated.emit)
        self._artwork.hero_ready.connect(self.heroUpdated.emit)
        self._artwork.fetch_finished.connect(self.artworkFetchFinished.emit)
        self._artwork.name_fetched.connect(self._on_name_fetched)
        self._artwork.install_dir_resolved.connect(self._on_install_dir_resolved)
        self._connect_theme_signal()

    @property
    def active_view(self) -> str:
        return self._active_view

    @property
    def modal_game_name(self) -> str:
        return self._modal_game_name

    # --- Games ---

    @pyqtSlot(result="QVariant")
    def getGames(self) -> list[dict]:
        return [_game_to_dict(g) for g in self._gm.get_games()]

    @pyqtSlot(str, result="QVariant")
    def getGame(self, name: str) -> dict:
        game = self._gm.get_game(name)
        return _game_to_modal_dict(self._gm, game) if game else {}

    @pyqtSlot(str, result="QVariant")
    def addGame(self, exe_path: str) -> dict:
        name = display_name_from_exe(exe_path)
        install_dir = find_game_root(exe_path) or str(Path(exe_path).parent)
        default_runner = str(self._gm.global_config.get("proton_version") or "")
        ok = self._gm.add_game(
            name=name, exe=exe_path, proton=default_runner, args="",
            install_dir=install_dir,
        )
        if ok:
            self._artwork.fetch_artwork(name, exe_path)
            return {
                "success": True,
                "game": {
                    "name": name,
                    "exe_path": exe_path,
                    "install_dir": install_dir,
                },
            }
        return {"success": False, "error": "Failed to add game"}

    @pyqtSlot(str, result="QVariant")
    def applyZipToGame(self, zip_path: str) -> dict:
        """Extract a zip into the modal game's install dir, set overrides + exe."""
        from crucible.core.zip import extract

        name = self.modal_game_name
        game = self._gm.get_game(name) if name else None
        if not game:
            return {"success": False, "error": "No game selected"}

        exe = game.get("exe_path", "")
        dest = game.get("install_dir")
        if dest and not Path(dest).is_dir():
            dest = ""
        if not dest:
            dest = find_game_root(exe)
        if not dest and exe:
            exe_path = Path(exe)
            if exe_path.exists():
                dest = str(exe_path.parent)
        if not dest:
            return {"success": False, "error": "No install directory"}

        try:
            contents = extract(zip_path, dest)
        except (ValueError, OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            _log.error("Zip extract failed for %s: %s", name, exc)
            return {"success": False, "error": str(exc)}

        added_dlls: list[str] = []
        updates: dict[str, Any] = {}
        if contents.dlls:
            existing = {
                d.strip() for d in game.get("custom_overrides", "").split(",") if d.strip()
            }
            new_set = set(contents.dlls)
            added_dlls = sorted(new_set - existing)
            merged = ",".join(sorted(existing | new_set))
            updates["custom_overrides"] = merged
            game["custom_overrides"] = merged

        new_exe = contents.exes[0] if contents.exes else ""
        if new_exe:
            old_exe = game.get("exe_path", "")
            self._artwork.migrate_artwork(old_exe, new_exe)
            updates["exe_path"] = new_exe
            updates["exe_match_mode"] = "custom"
            game["exe_path"] = new_exe
            game["exe_match_mode"] = "custom"

        if updates:
            try:
                _write_game_updates(self._gm, Path(game["game_file"]), updates)
                self._gm.scan_games()
            except (OSError, TypeError, ValueError) as exc:
                _log.error("Failed to update game after zip apply for %s: %s", name, exc)
                return {"success": False, "error": str(exc)}

        return {
            "success": True,
            "dlls": contents.dlls,
            "added_dlls": added_dlls,
            "exe": new_exe,
        }

    @pyqtSlot(str, result=bool)
    def clearGameLogs(self, name: str) -> bool:
        ok = self._gm.clear_game_logs(name)
        if ok:
            self.toastRequested.emit("Logs cleared", "success")
        return ok

    @pyqtSlot(str, result=bool)
    def resetGamePrefix(self, name: str) -> bool:
        ok = self._gm.reset_game_prefix(name)
        if ok:
            self.toastRequested.emit("Wine prefix reset", "success")
        return ok

    @pyqtSlot(str, result=bool)
    def deleteGameFull(self, name: str) -> bool:
        ok = self._gm.delete_game(name)
        if ok:
            self.toastRequested.emit("Game removed", "success")
        return ok

    @pyqtSlot(str, result=str)
    def launchGame(self, name: str) -> str:
        return self._gm.launch_game(name) or ""

    @pyqtSlot(str, result=bool)
    def stopGame(self, name: str) -> bool:
        return self._gm.stop_game(name)

    @pyqtSlot(str, result=bool)
    def isGameRunning(self, name: str) -> bool:
        return self._gm.is_game_running(name)

    @pyqtSlot(str, str, "QVariant", result=bool)
    def updateGameField(self, name: str, field: str, value) -> bool:
        game = self._gm.get_game(name)
        if not game:
            return False
        if field == "name":
            new_name = str(value).strip()
            if not new_name:
                return False
            return self._gm.rename_game(name, new_name)
        if field == "exe_path":
            new_exe = str(value).strip()
            if not new_exe:
                return False
            old_exe = game.get("exe_path", "")
            updates = {"exe_path": new_exe, "exe_match_mode": "custom"}
            if Path(new_exe).exists():
                updates["install_dir"] = find_game_root(new_exe) or str(Path(new_exe).resolve().parent)
            ok = self._gm.update_game_fields(name, updates)
            if ok:
                self._artwork.migrate_artwork(old_exe, new_exe)
            return ok
        if field in ("enable_gamemode", "enable_mangohud", "enable_gamescope"):
            disabled_flags = {
                str(key) for key in (game.get("disabled_global_flags") or []) if str(key).strip()
            }
            if value:
                disabled_flags.discard(field)
                return self._gm.update_game_fields(
                    name,
                    {field: True, "disabled_global_flags": sorted(disabled_flags)},
                )
            disabled_flags.add(field)
            return self._gm.update_game_fields(
                name,
                {field: False, "disabled_global_flags": sorted(disabled_flags)},
            )
        if field == "env_vars":
            env_vars = dict(value or {})
            disabled_env_vars = {
                str(key) for key in (game.get("disabled_env_vars") or []) if str(key).strip()
            }
            for env_key in env_vars:
                disabled_env_vars.discard(str(env_key))
            return self._gm.update_game_fields(
                name,
                {"env_vars": env_vars, "disabled_env_vars": sorted(disabled_env_vars)},
            )
        return self._gm.update_game_fields(name, {field: value})

    @pyqtSlot(str, str, str, bool, result=bool)
    def setGameEnvOverride(self, name: str, env_key: str, env_value: str, enabled: bool) -> bool:
        game = self._gm.get_game(name)
        if not game:
            return False
        global_env = dict(self._gm.global_config.get("env_vars") or {})
        env_vars = dict(game.get("env_vars") or {})
        disabled_env_vars = {
            str(key) for key in (game.get("disabled_env_vars") or []) if str(key).strip()
        }
        if enabled:
            disabled_env_vars.discard(env_key)
            if env_key in global_env:
                env_vars.pop(env_key, None)
            else:
                env_vars[env_key] = env_value
        else:
            env_vars.pop(env_key, None)
            if env_key in global_env:
                disabled_env_vars.add(env_key)
        return self._gm.update_game_fields(
            name,
            {
                "env_vars": env_vars,
                "disabled_env_vars": sorted(disabled_env_vars),
            },
        )

    @pyqtSlot(str, result="QVariant")
    def createShortcut(self, name: str) -> dict:
        game = self._gm.get_game(name)
        if not game:
            return {"success": False, "message": "Game not found"}
        ok, msg = self._gm.create_game_shortcut(game)
        return {"success": ok, "message": "Shortcut created" if ok else msg}

    @pyqtSlot(str, result=bool)
    def hasShortcut(self, name: str) -> bool:
        return self._gm.has_game_shortcut(name)

    @pyqtSlot(str, result=bool)
    def removeShortcut(self, name: str) -> bool:
        return self._gm.remove_game_shortcut(name)

    # --- Artwork ---

    @pyqtSlot(str, result=bool)
    def removeUmuConfig(self, name: str) -> bool:
        """Clear UMU/Proton-owned config fields for a game."""
        game = self._gm.get_game(name)
        if not game:
            return False
        env_vars = dict(game.get("env_vars") or {})
        disabled_env_vars = {
            str(key) for key in (game.get("disabled_env_vars") or []) if str(key).strip()
        }
        for key in (
            "UMU_RUNTIME_UPDATE",
            "UMU_LOG",
            "PROTON_LOG_DIR",
            "PROTON_VERB",
            "PROTON_NO_ESYNC",
            "PROTON_NO_FSYNC",
        ):
            env_vars.pop(key, None)
            disabled_env_vars.discard(key)
        ok = self._gm._update_game_record(
            Path(game["game_file"]),
            {
                "proton_version": "",
                "proton_path": "",
                "env_vars": env_vars,
                "disabled_env_vars": sorted(disabled_env_vars),
            },
        )
        if ok:
            self.toastRequested.emit("UMU config cleared", "success")
        return ok

    @pyqtSlot(str)
    def openGameLogDir(self, name: str) -> None:
        """Open the per-game log directory in the system file manager."""
        from crucible.core.paths import clean_env
        log_dir = Paths.game_logs_dir(name)
        try:
            subprocess.Popen(
                ["xdg-open", str(log_dir)],
                env=clean_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            _log.error("Failed to open log dir: %s", exc)
            self.toastRequested.emit("Failed to open log directory", "error")

    @pyqtSlot(str, result=str)
    def getPortraitArtworkPath(self, exe_path: str) -> str:
        """Return portrait artwork path, falling back to header."""
        portrait = self._artwork._has_cached_art(exe_path=exe_path, variant='portrait')
        if portrait:
            return portrait
        return self._artwork._has_cached_art(exe_path=exe_path) or ""

    @pyqtSlot(str, result=str)
    def getHeroArtworkPath(self, exe_path: str) -> str:
        """Return hero banner path, falling back to header."""
        hero = self._artwork._has_cached_art(exe_path=exe_path, variant='hero')
        if hero:
            return hero
        return self._artwork._has_cached_art(exe_path=exe_path) or ""

    # --- Artwork callbacks ---

    def _on_name_fetched(self, old_name: str, new_name: str) -> None:
        game = self._gm.get_game(old_name)
        if game and old_name != new_name:
            self._gm.rename_game(old_name, new_name)

    def _on_install_dir_resolved(self, game_name: str, install_dir: str) -> None:
        game = self._gm.get_game(game_name)
        if game and game.get("exe_match_mode") != "custom":
            self._gm.update_install_dir(game_name, install_dir)
