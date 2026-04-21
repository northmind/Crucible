"""Game state machine — prevents double-launch and tracks lifecycle.

States::

    IDLE → LAUNCHING → RUNNING → STOPPING → IDLE
                                     ↑
                                     └── (crash / exit) → IDLE

All transitions are guarded by a single lock so concurrent launch/stop
calls are serialised.
"""

from __future__ import annotations

import enum
import logging
import threading

logger = logging.getLogger(__name__)


class GameState(enum.Enum):
    """Lifecycle states for a single game."""

    IDLE = "idle"
    LAUNCHING = "launching"
    RUNNING = "running"
    STOPPING = "stopping"


# Valid transitions: current_state → set of allowed next states.
_TRANSITIONS: dict[GameState, frozenset[GameState]] = {
    GameState.IDLE: frozenset({GameState.LAUNCHING}),
    GameState.LAUNCHING: frozenset({GameState.RUNNING, GameState.IDLE}),
    GameState.RUNNING: frozenset({GameState.STOPPING, GameState.IDLE}),
    GameState.STOPPING: frozenset({GameState.IDLE}),
}


class GameStateTracker:
    """Thread-safe state machine for all known games.

    Unknown game names are implicitly in ``IDLE`` state.
    """

    def __init__(self) -> None:
        self._states: dict[str, GameState] = {}
        self._lock = threading.Lock()

    def get(self, game_name: str) -> GameState:
        """Return the current state for *game_name* (default IDLE)."""
        with self._lock:
            return self._states.get(game_name, GameState.IDLE)

    def transition(self, game_name: str, target: GameState) -> bool:
        """Attempt to move *game_name* to *target* state.

        Returns True on success, False if the transition is invalid.
        """
        with self._lock:
            current = self._states.get(game_name, GameState.IDLE)
            allowed = _TRANSITIONS.get(current, frozenset())
            if target not in allowed:
                logger.warning(
                    "Invalid state transition for %s: %s → %s",
                    game_name, current.value, target.value,
                )
                return False
            if target == GameState.IDLE:
                self._states.pop(game_name, None)
            else:
                self._states[game_name] = target
            return True

    def force_idle(self, game_name: str) -> None:
        """Unconditionally reset *game_name* to IDLE (crash recovery)."""
        with self._lock:
            self._states.pop(game_name, None)

