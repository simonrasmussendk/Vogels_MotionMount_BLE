"""Data models for the Vogels MotionMount BLE integration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .coordinator import VogelsMotionMountCoordinator


class ConnectionState(str, Enum):
    """High-level BLE connection state exposed to entities."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class VogelsMotionMountData:
    """Data for the Vogels MotionMount BLE integration."""

    coordinator: VogelsMotionMountCoordinator


@dataclass
class TelemetryData:
    """Telemetry data from the MotionMount."""

    extension_current: int | None = None
    turn_current: int | None = None
    extension_target: int | None = None
    turn_target: int | None = None
    is_moving: bool | None = None

    def update_from_line(self, line: str) -> tuple[bool, bool]:
        """Update telemetry data from a parsed line.

        Returns a tuple ``(recognized, changed)`` where ``recognized`` is
        True if the line matched any known telemetry format and
        ``changed`` is True if the stored value actually changed.
        """
        import re
        from .const import (
            TELEMETRY_EXTENSION_CURRENT_PATTERN,
            TELEMETRY_TURN_CURRENT_PATTERN,
            TELEMETRY_EXTENSION_TARGET_PATTERN,
            TELEMETRY_TURN_TARGET_PATTERN,
            TELEMETRY_MOVING_PATTERN,
        )

        # Turn values are inverted: the device reports +100 for "full left"
        # and -100 for "full right", but we expose slider-intuitive signs
        # (-100 = left, +100 = right) throughout the integration.
        def _neg_int(v: str) -> int:
            return -int(v)

        # (pattern, attribute, converter)
        fields: tuple[tuple[str, str, Any], ...] = (
            (TELEMETRY_EXTENSION_CURRENT_PATTERN, "extension_current", int),
            (TELEMETRY_TURN_CURRENT_PATTERN, "turn_current", _neg_int),
            (TELEMETRY_EXTENSION_TARGET_PATTERN, "extension_target", int),
            (TELEMETRY_TURN_TARGET_PATTERN, "turn_target", _neg_int),
            (TELEMETRY_MOVING_PATTERN, "is_moving", lambda v: bool(int(v))),
        )

        recognized = False
        changed = False
        for pattern, attr, converter in fields:
            if match := re.search(pattern, line):
                recognized = True
                new_value = converter(match.group(1))
                if getattr(self, attr) != new_value:
                    setattr(self, attr, new_value)
                    changed = True

        return recognized, changed


@dataclass
class ConnectionStats:
    """Connection statistics for diagnostics."""
    
    connection_attempts: int = 0
    successful_connections: int = 0
    disconnections: int = 0
    last_error: str | None = None
    last_telemetry_time: float | None = None
    telemetry_lines_received: int = 0
    is_connected: bool = False
    current_adapter: str | None = None
