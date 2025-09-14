"""Diagnostics support for Vogels MotionMount BLE integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import VogelsMotionMountData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: VogelsMotionMountData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator
    connection = coordinator.connection
    
    # Get connection statistics
    stats = connection.connection_stats
    
    # Get current telemetry data
    telemetry = connection.telemetry_data
    
    # Redact sensitive information
    redacted_address = _redact_address(coordinator.device_address)
    
    diagnostics = {
        "device_info": {
            "name": coordinator.device_name,
            "address": redacted_address,
            "adapter": stats.current_adapter,
        },
        "connection_stats": {
            "is_connected": stats.is_connected,
            "connection_attempts": stats.connection_attempts,
            "successful_connections": stats.successful_connections,
            "disconnections": stats.disconnections,
            "last_error": stats.last_error,
            "last_telemetry_time": stats.last_telemetry_time,
            "telemetry_lines_received": stats.telemetry_lines_received,
        },
        "current_telemetry": {
            "extension_current": telemetry.extension_current,
            "turn_current": telemetry.turn_current,
            "is_moving": telemetry.is_moving,
        },
        "configuration": {
            "auto_disconnect_timeout": coordinator._get_auto_disconnect_timeout(),
            "debug_raw_data": coordinator._get_debug_raw_data(),
            "uuids": coordinator._get_uuids(),
        },
        "coordinator_state": {
            "available": coordinator.available,
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval) if coordinator.update_interval else None,
        },
    }
    
    return diagnostics


def _redact_address(address: str) -> str:
    """Redact device address for privacy."""
    if ":" in address:  # MAC address format
        parts = address.split(":")
        if len(parts) == 6:
            # Show first and last octet, redact middle
            return f"{parts[0]}:**:**:**:**:{parts[-1]}"
    elif "-" in address:  # Some identifier formats
        parts = address.split("-")
        if len(parts) > 2:
            return f"{parts[0]}-***-{parts[-1]}"
    
    # Fallback: show first and last 4 characters
    if len(address) > 8:
        return f"{address[:4]}***{address[-4:]}"
    
    return "***"
