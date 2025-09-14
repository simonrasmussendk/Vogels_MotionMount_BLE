"""Data models for the Vogels MotionMount BLE integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import VogelsMotionMountCoordinator


@dataclass
class VogelsMotionMountData:
    """Data for the Vogels MotionMount BLE integration."""
    
    coordinator: VogelsMotionMountCoordinator


@dataclass
class TelemetryData:
    """Telemetry data from the MotionMount."""
    
    extension_current: int | None = None
    turn_current: int | None = None
    is_moving: bool | None = None
    
    def update_from_line(self, line: str) -> bool:
        """Update telemetry data from a parsed line.
        
        Returns True if any value was updated.
        """
        updated = False
        
        # Parse extension current
        import re
        from .const import (
            TELEMETRY_EXTENSION_PATTERN,
            TELEMETRY_TURN_PATTERN,
            TELEMETRY_MOVING_PATTERN,
        )
        
        if match := re.search(TELEMETRY_EXTENSION_PATTERN, line):
            new_value = int(match.group(1))
            if self.extension_current != new_value:
                self.extension_current = new_value
                updated = True
        
        # Parse turn current
        if match := re.search(TELEMETRY_TURN_PATTERN, line):
            new_value = int(match.group(1))
            if self.turn_current != new_value:
                self.turn_current = new_value
                updated = True
        
        # Parse moving state
        if match := re.search(TELEMETRY_MOVING_PATTERN, line):
            new_value = bool(int(match.group(1)))
            if self.is_moving != new_value:
                self.is_moving = new_value
                updated = True
        
        return updated


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
