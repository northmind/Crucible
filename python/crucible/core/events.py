"""Lightweight event bus for decoupled communication.

Central hub that lets core/backend emit events (game launched, config
changed, proton installed, etc.) without direct references to UI widgets
or other subsystems.  Any component can connect to the bus signals.

Usage::

    from crucible.core.events import event_bus

    # Emitter side (core, worker, etc.)
    event_bus.game_state_changed.emit("My Game", "running")

    # Listener side (UI widget, tray icon, etc.)
    event_bus.game_state_changed.connect(self._on_game_state_changed)
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """Singleton event bus using Qt signals.

    All signals carry enough context to be consumed without additional
    lookups.  Names follow ``subject_verb`` convention.
    """

    # Game lifecycle
    game_state_changed = pyqtSignal(str, str)   # game_name, new_state
    game_launched = pyqtSignal(str)              # game_name
    game_exited = pyqtSignal(str)                # game_name

    # Configuration
    config_changed = pyqtSignal(str, object)     # key, new_value
    global_config_changed = pyqtSignal()         # any global default changed

    # Proton / runner management
    proton_installed = pyqtSignal(str)           # version_name
    proton_removed = pyqtSignal(str)             # version_name

    # Game library
    game_added = pyqtSignal(str)                 # game_name
    game_removed = pyqtSignal(str)               # game_name
    game_updated = pyqtSignal(str)               # game_name
    library_refreshed = pyqtSignal()             # full rescan completed

    # Notifications
    notification = pyqtSignal(str, str)          # title, message


# Module-level singleton — import this, not the class.
event_bus = EventBus()
