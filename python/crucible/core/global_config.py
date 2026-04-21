"""Global configuration with per-game override inheritance.

GlobalConfig stores default values for Proton version, env vars, launch args,
wrapper command, DLL overrides, and tool toggles.  Per-game configs store only
overrides — anything not set on a game falls through to the global default.

Storage: ``~/.local/share/crucible-launcher/global_config.json``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crucible.core.game_utils import _load_json_file, _write_json_file
from crucible.core.paths import Paths

logger = logging.getLogger(__name__)

# Keys that support inheritance (game value overrides global default).
INHERITABLE_KEYS: tuple[str, ...] = (
    "proton_version",
    "launch_args",
    "custom_overrides",
    "env_vars",
    "wrapper_command",
    "fingerprint_lock",

    "enable_gamemode",
    "enable_mangohud",
    "enable_gamescope",
    "gamescope_settings",
)

INHERITABLE_BOOL_KEYS: tuple[str, ...] = (
    "fingerprint_lock",
    "enable_gamemode",
    "enable_mangohud",
    "enable_gamescope",
)

# Default values for a fresh install — conservative, nothing enabled.
_FACTORY_DEFAULTS: dict[str, Any] = {
    "proton_version": "",
    "launch_args": "",
    "custom_overrides": "",
    "env_vars": {},
    "wrapper_command": "",
    "fingerprint_lock": False,

    "enable_gamemode": False,
    "enable_mangohud": False,
    "enable_gamescope": False,
    "gamescope_settings": {},
}


class GlobalConfig:
    """Singleton-style global defaults that per-game configs inherit from.

    Call :meth:`get` for individual keys or :meth:`resolve` to merge a full
    game dict with global defaults (game values win over globals).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or (Paths.data_dir() / "global_config.json")
        self._data: dict[str, Any] = dict(_FACTORY_DEFAULTS)
        self._load()

    # -- Persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            stored = _load_json_file(self._path)
            for key in INHERITABLE_KEYS:
                if key in stored:
                    self._data[key] = stored[key]
        except (OSError, ValueError, KeyError) as exc:
            logger.error("Failed to load global config: %s", exc)

    def save(self) -> None:
        """Persist current global defaults to disk (atomic write)."""
        try:
            _write_json_file(self._path, self._data)
        except OSError as exc:
            logger.error("Failed to save global config: %s", exc)

    # -- Accessors ---------------------------------------------------------

    def get(self, key: str, fallback: Any = None) -> Any:
        """Return the global default for *key*, or *fallback* if unset."""
        return self._data.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        """Set a global default and persist."""
        self._data[key] = value
        self.save()

    def set_many(self, updates: dict[str, Any]) -> None:
        """Update multiple global defaults at once and persist."""
        self._data.update(updates)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of all global defaults."""
        return dict(self._data)

    # -- Merge / resolve ---------------------------------------------------

    def resolve(self, game: dict[str, Any]) -> dict[str, Any]:
        """Return a merged dict: global defaults + game overrides.

        For dict-valued keys (``env_vars``, ``gamescope_settings``), the game
        dict is merged *on top of* the global dict so per-game entries win but
        globals are preserved for keys the game doesn't override.

        For scalar keys, any non-empty game value replaces the global default.
        An explicitly empty string (``""``) in the game config means
        "no override — use global default".
        """
        merged: dict[str, Any] = dict(game)
        disabled_env_vars = {
            str(key) for key in (game.get("disabled_env_vars") or []) if str(key).strip()
        }
        disabled_flags = {
            str(key) for key in (game.get("disabled_global_flags") or []) if str(key).strip()
        }
        for key in INHERITABLE_KEYS:
            global_val = self._data.get(key)
            game_val = game.get(key)

            if key in ("env_vars", "gamescope_settings"):
                # Dict merge: global provides base, game overrides on top
                base = dict(global_val) if isinstance(global_val, dict) else {}
                if key == "env_vars" and disabled_env_vars:
                    for env_key in disabled_env_vars:
                        base.pop(env_key, None)
                overlay = game_val if isinstance(game_val, dict) else {}
                base.update(overlay)
                merged[key] = base
            elif key in INHERITABLE_BOOL_KEYS:
                # Legacy stored False inherits; explicit off is tracked separately.
                if key in disabled_flags:
                    merged[key] = False
                elif game_val is True:
                    merged[key] = True
                elif global_val is not None:
                    merged[key] = global_val
            else:
                # Scalar: empty/missing game value → use global
                if not game_val and global_val:
                    merged[key] = global_val

        return merged
