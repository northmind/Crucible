"""Lightweight event bus for decoupled communication.

Central hub that lets core/backend emit events (game launched, config
changed, proton installed, etc.) without direct references to UI widgets
or other subsystems.  Any component can connect to the bus signals.

Usage::

    from crucible.core.events import event_bus

    # Emitter side (core, worker, etc.)
    event_bus.game_launched.emit("My Game")

    # Listener side (UI widget, tray icon, etc.)
    event_bus.game_launched.connect(self._on_game_launched)
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """Singleton event bus using Qt signals.

    All signals carry enough context to be consumed without additional
    lookups.  Names follow ``subject_verb`` convention.
    """

    # Game lifecycle
    game_launched = pyqtSignal(str)              # game_name
    game_exited = pyqtSignal(str)                # game_name

    # Game library
    library_refreshed = pyqtSignal()             # full rescan completed



# Module-level singleton — import this, not the class.
event_bus = EventBus()
