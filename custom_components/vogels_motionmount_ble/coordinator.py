"""Coordinator for Vogels MotionMount BLE integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connection import VogelsMotionMountConnection
from .const import (
    CONF_ADAPTER,
    CONF_AUTO_DISCONNECT_TIMEOUT,
    CONF_DEBUG_RAW_DATA,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    CONF_LOG_LEVEL,
    CONF_UUID_EXTENSION_TARGET,
    CONF_UUID_NUS_TX,
    CONF_UUID_PRESET,
    CONF_UUID_TURN_TARGET,
    DEFAULT_AUTO_DISCONNECT_TIMEOUT,
    DEFAULT_LOG_LEVEL,
    DOMAIN,
    LOGGER_NAME,
)
from .models import TelemetryData

_LOGGER = logging.getLogger(__name__)


class VogelsMotionMountCoordinator(DataUpdateCoordinator[TelemetryData]):
    """Coordinator for Vogels MotionMount BLE device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_DEVICE_NAME]}",
            update_interval=None,  # We use push updates via notifications
        )
        
        self.entry = entry
        self.device_name = entry.data[CONF_DEVICE_NAME]
        self.device_address = entry.data[CONF_DEVICE_ADDRESS]
        
        # Configure logging level
        self._setup_logging()
        
        # Create connection manager
        self._connection = VogelsMotionMountConnection(
            hass=hass,
            device_address=self.device_address,
            adapter=entry.data.get(CONF_ADAPTER),
            uuids=self._get_uuids(),
            auto_disconnect_timeout=self._get_auto_disconnect_timeout(),
            debug_raw_data=self._get_debug_raw_data(),
        )
        
        # Set telemetry callback
        self._connection.set_telemetry_callback(self._handle_telemetry_update)
        
        # Track if we've received initial data
        self._initial_data_received = False
        
        # Periodic health check task
        self._health_check_task: asyncio.Task | None = None

    def _setup_logging(self) -> None:
        """Configure logging level for this coordinator."""
        log_level = self.entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)
        
        # Get the logger for our component
        component_logger = logging.getLogger(LOGGER_NAME)
        
        # Set the log level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        component_logger.setLevel(numeric_level)
        
        _LOGGER.debug("Set logging level to %s for %s", log_level, self.device_name)

    def _get_uuids(self) -> dict[str, str]:
        """Get GATT UUIDs from config."""
        return {
            "nus_tx": self.entry.options.get(CONF_UUID_NUS_TX, self.entry.data.get(CONF_UUID_NUS_TX)),
            "extension_target": self.entry.options.get(
                CONF_UUID_EXTENSION_TARGET, self.entry.data.get(CONF_UUID_EXTENSION_TARGET)
            ),
            "turn_target": self.entry.options.get(
                CONF_UUID_TURN_TARGET, self.entry.data.get(CONF_UUID_TURN_TARGET)
            ),
            "preset": self.entry.options.get(CONF_UUID_PRESET, self.entry.data.get(CONF_UUID_PRESET)),
        }

    def _get_auto_disconnect_timeout(self) -> int:
        """Get auto-disconnect timeout from config."""
        return self.entry.options.get(
            CONF_AUTO_DISCONNECT_TIMEOUT, DEFAULT_AUTO_DISCONNECT_TIMEOUT
        )

    def _get_debug_raw_data(self) -> bool:
        """Get debug raw data flag from config."""
        return self.entry.options.get(CONF_DEBUG_RAW_DATA, False)

    @property
    def connection(self) -> VogelsMotionMountConnection:
        """Return the connection manager."""
        return self._connection

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        _LOGGER.info("Setting up coordinator for %s", self.device_name)
        
        # Don't attempt initial connection - connect only when user performs actions
        _LOGGER.info("Coordinator setup complete for %s (on-demand connection mode)", self.device_name)
        
        # Don't start automatic health check - connect only on demand

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.info("Shutting down coordinator for %s", self.device_name)
        await self._connection.async_shutdown()

    def _handle_telemetry_update(self, telemetry_data: TelemetryData) -> None:
        """Handle telemetry data updates from the connection."""
        _LOGGER.debug(
            "Telemetry update for %s: ext=%s, turn=%s, moving=%s",
            self.device_name,
            telemetry_data.extension_current,
            telemetry_data.turn_current,
            telemetry_data.is_moving,
        )
        
        # Update coordinator data
        self.async_set_updated_data(telemetry_data)
        
        # Mark that we've received initial data
        if not self._initial_data_received:
            self._initial_data_received = True
            _LOGGER.info("Received initial telemetry data for %s", self.device_name)

    async def _async_update_data(self) -> TelemetryData:
        """Update data - not used since we rely on push notifications."""
        # This method is required by DataUpdateCoordinator but we don't use it
        # since we get updates via BLE notifications
        if not self._connection.is_connected:
            # Try to reconnect
            if not await self._connection.async_connect():
                raise UpdateFailed("Device not connected and reconnection failed")
        
        return self._connection.telemetry_data

    async def async_write_extension_target(self, value: int) -> bool:
        """Write extension target value."""
        _LOGGER.debug("Writing extension target %d for %s", value, self.device_name)
        return await self._connection.async_write_target("extension_target", value)

    async def async_write_turn_target(self, value: int) -> bool:
        """Write turn target value."""
        _LOGGER.debug("Writing turn target %d for %s", value, self.device_name)
        return await self._connection.async_write_target("turn_target", value)

    async def async_write_preset(self, preset_index: int) -> bool:
        """Write preset index."""
        _LOGGER.info("Coordinator: Writing preset %d for %s (connected: %s)", 
                    preset_index, self.device_name, self._connection.is_connected)
        result = await self._connection.async_write_preset(preset_index)
        _LOGGER.info("Coordinator: Preset %d write result: %s", preset_index, result)
        return result

    async def async_stop_movement(self) -> bool:
        """Stop movement by setting targets to current positions."""
        _LOGGER.info("Coordinator: Stop movement requested for %s", self.device_name)
        telemetry = self._connection.telemetry_data
        
        if telemetry.extension_current is None or telemetry.turn_current is None:
            _LOGGER.warning("Cannot stop movement - current positions unknown")
            return False
        
        _LOGGER.info(
            "Stopping movement for %s (ext=%d, turn=%d)",
            self.device_name,
            telemetry.extension_current,
            telemetry.turn_current,
        )
        
        # Write both targets to current positions
        ext_success = await self.async_write_extension_target(telemetry.extension_current)
        turn_success = await self.async_write_turn_target(telemetry.turn_current)
        
        result = ext_success and turn_success
        _LOGGER.info("Coordinator: Stop movement result: %s", result)
        return result

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information for device registry."""
        return {
            "identifiers": {(DOMAIN, self.device_address)},
            "name": self.device_name,
            "manufacturer": "Vogels",
            "model": "MotionMount",
            "sw_version": "1.0",
            "via_device": (DOMAIN, self.device_address),
        }

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        # In on-demand mode, entities are always available - connection happens when needed
        return True
