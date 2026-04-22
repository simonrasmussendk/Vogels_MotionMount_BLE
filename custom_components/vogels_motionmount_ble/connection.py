"""BLE connection manager for Vogels MotionMount."""
from __future__ import annotations

import asyncio
import logging
import random
import struct
import time
from typing import Any, Callable

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

from .const import (
    CONNECTION_TIMEOUT,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_BASE_DELAY,
    RECONNECT_JITTER_MAX,
    RECONNECT_MAX_DELAY,
)
from .models import ConnectionState, ConnectionStats, TelemetryData

# Maximum time we allow a BLE disconnect to take before moving on.
# Without this bound, a stuck underlying stack can make Home Assistant's
# "unload entry" step hang — which is what causes the options-flow crash.
_DISCONNECT_TIMEOUT: float = 5.0
# Maximum time we allow any single GATT write to take.
_WRITE_TIMEOUT: float = 10.0

_LOGGER = logging.getLogger(__name__)


async def auto_discover_uuids(client: BleakClient, device_address: str) -> dict[str, str]:
    """Auto-discover UUIDs for MotionMount characteristics based on service patterns and properties."""
    discovered_uuids = {}
    
    try:
        # Handle Home Assistant's BLE client wrapper
        services = None
        try:
            services = await client.get_services()
        except AttributeError:
            if hasattr(client, '_client'):
                services = await client._client.get_services()
            elif hasattr(client, 'services'):
                services = client.services
            else:
                _LOGGER.error("Cannot access BLE services for auto-discovery")
                return {}
        
        services_list = list(services) if services else []
        
        # Analyze characteristics with detailed inspection
        nus_tx_candidates = []
        extension_target_candidates = []
        turn_target_candidates = []
        preset_candidates = []
        
        for service in services_list:
            # Skip standard Bluetooth services
            if any(std_uuid in service.uuid.lower() for std_uuid in 
                  ["00001800", "00001801", "0000fe59", "0000180a", "0000180f"]):
                continue
            
            for char in service.characteristics:
                properties = char.properties
                char_info = {
                    'uuid': char.uuid,
                    'service_uuid': service.uuid,
                    'properties': properties,
                    'descriptors': []
                }
                
                # Collect descriptor information
                for desc in char.descriptors:
                    char_info['descriptors'].append({
                        'uuid': desc.uuid,
                        'handle': getattr(desc, 'handle', None)
                    })
                
                # Nordic UART Service TX: notify-only in NUS service
                if ("notify" in properties and "read" not in properties and 
                    "write" not in properties and "indicate" not in properties):
                    is_nus = "6e400001" in service.uuid.lower()
                    priority = 1 if is_nus else 2
                    nus_tx_candidates.append((priority, char_info))
                
                # Target characteristics: read+write+notify
                elif ("read" in properties and "write" in properties and "notify" in properties):
                    # Try to read current value to help distinguish characteristics
                    try:
                        # Attempt to read current value for analysis
                        current_value = await client.read_gatt_char(char.uuid)
                        char_info['current_value'] = current_value
                        char_info['value_length'] = len(current_value) if current_value else 0
                        
                        # Analyze value patterns to distinguish extension vs turn
                        if current_value and len(current_value) >= 2:
                            # Extension targets often have different value ranges than turn targets
                            value_int = int.from_bytes(current_value[:2], byteorder='little', signed=True)
                            char_info['value_int'] = value_int
                            
                            # Add to both lists - we'll sort them later based on multiple criteria
                            extension_target_candidates.append(char_info)
                            turn_target_candidates.append(char_info)
                        else:
                            # Fallback: add to both lists for later analysis
                            extension_target_candidates.append(char_info)
                            turn_target_candidates.append(char_info)
                            
                    except Exception as read_err:
                        _LOGGER.debug("Could not read characteristic %s for analysis: %s", char.uuid, read_err)
                        # Add to both lists if we can't read the value
                        extension_target_candidates.append(char_info)
                        turn_target_candidates.append(char_info)
                
                # Preset characteristic: write-only (but not Nordic UART RX)
                elif ("write" in properties and "read" not in properties and 
                      "notify" not in properties and "indicate" not in properties):
                    # Exclude Nordic UART Service characteristics from preset candidates
                    if "6e400001" not in service.uuid.lower():
                        preset_candidates.append(char_info)
        
        # Assign NUS TX (telemetry) - prefer Nordic UART Service
        if nus_tx_candidates:
            nus_tx_candidates.sort(key=lambda x: x[0])  # Sort by priority
            best_nus = nus_tx_candidates[0][1]
            discovered_uuids["nus_tx"] = best_nus['uuid']
            _LOGGER.debug("Auto-discovered NUS TX (telemetry): %s in service %s", 
                        best_nus['uuid'], best_nus['service_uuid'])
        
        # Assign extension and turn targets using multiple criteria
        if extension_target_candidates and turn_target_candidates:
            # Create scoring system for better characteristic identification
            def score_characteristic(char_info, target_type):
                score = 0
                value = char_info.get('value_int', 0)
                uuid_lower = char_info['uuid'].lower()
                
                if target_type == 'extension':
                    # Extension target preferences:
                    # 1. Values in typical extension range (0-650mm)
                    if 0 <= abs(value) <= 650:
                        score += 10
                    # 2. Higher absolute values are more likely extension
                    score += min(abs(value) / 100, 10)
                    # 3. UUID pattern hints (if available)
                    if 'fa25' in uuid_lower:
                        score += 50
                    elif 'fa01' in uuid_lower:
                        score += 5  # Lower priority for fa01
                        
                elif target_type == 'turn':
                    # Turn target preferences:
                    # 1. Values in typical turn range (-90 to +90 degrees)
                    if -90 <= value <= 90:
                        score += 10
                    # 2. Lower absolute values are more likely turn
                    score += max(10 - abs(value) / 10, 0)
                    # 3. UUID pattern hints (if available)
                    if 'fa27' in uuid_lower:
                        score += 50
                        
                return score
            
            # Score all candidates for extension
            extension_scored = [(score_characteristic(char, 'extension'), char) 
                              for char in extension_target_candidates]
            extension_scored.sort(key=lambda x: x[0], reverse=True)
            
            # Score all candidates for turn
            turn_scored = [(score_characteristic(char, 'turn'), char) 
                         for char in turn_target_candidates]
            turn_scored.sort(key=lambda x: x[0], reverse=True)
            
            # Assign extension target (highest scoring)
            if extension_scored:
                best_ext = extension_scored[0][1]
                discovered_uuids["extension_target"] = best_ext['uuid']
                _LOGGER.debug("Auto-discovered Extension Target: %s in service %s (value: %s, score: %s)", 
                        best_ext['uuid'], best_ext['service_uuid'], 
                        best_ext.get('value_int', 'unknown'), extension_scored[0][0])
            
            # Assign turn target (highest scoring, but not same as extension)
            for score, candidate in turn_scored:
                if candidate['uuid'] != discovered_uuids.get("extension_target"):
                    discovered_uuids["turn_target"] = candidate['uuid']
                    _LOGGER.debug("Auto-discovered Turn Target: %s in service %s (value: %s, score: %s)", 
                                candidate['uuid'], candidate['service_uuid'], 
                                candidate.get('value_int', 'unknown'), score)
                    break
        
        # Assign preset characteristic - look for specific UUID pattern
        if preset_candidates:
            # Look for the correct preset characteristic with FA2A pattern
            best_preset = None
            for candidate in preset_candidates:
                uuid_lower = candidate['uuid'].lower()
                if 'fa2a' in uuid_lower:
                    best_preset = candidate
                    break
            
            # Fallback to first candidate if FA2A not found
            if not best_preset:
                best_preset = preset_candidates[0]
            
            discovered_uuids["preset"] = best_preset['uuid']
            _LOGGER.debug("Auto-discovered Preset: %s in service %s", 
                        best_preset['uuid'], best_preset['service_uuid'])
        
        _LOGGER.info("Auto-discovery complete. Found %d/4 required UUIDs: %s", 
                    len(discovered_uuids), list(discovered_uuids.keys()))
        return discovered_uuids
        
    except Exception as err:
        _LOGGER.error("Error during UUID auto-discovery for device %s: %s", device_address, err)
        return {}


async def discover_device_services(client: BleakClient, device_address: str) -> None:
    """Discover and log all services, characteristics, and descriptors for a BLE device."""
    try:
        _LOGGER.info("=== BLE DISCOVERY START for device %s ===", device_address)
        
        # Handle Home Assistant's BLE client wrapper
        services = None
        try:
            services = await client.get_services()
        except AttributeError:
            # Try to access the underlying Bleak client
            if hasattr(client, '_client'):
                services = await client._client.get_services()
            elif hasattr(client, 'services'):
                services = client.services
            else:
                _LOGGER.error("Cannot access BLE services - client type: %s", type(client).__name__)
                return
        
        # Convert services to list if it's a BleakGATTServiceCollection
        services_list = list(services) if services else []
        _LOGGER.info("Found %d services on device %s", len(services_list), device_address)
        
        for service_idx, service in enumerate(services_list, 1):
            _LOGGER.info(
                "Service %d/%d: UUID=%s, Description='%s'",
                service_idx,
                len(services_list),
                service.uuid,
                service.description or "No description"
            )
            
            if service.characteristics:
                _LOGGER.info("  Found %d characteristics in service %s", len(service.characteristics), service.uuid)
                
                for char_idx, char in enumerate(service.characteristics, 1):
                    # Get characteristic properties
                    properties = []
                    if "read" in char.properties:
                        properties.append("READ")
                    if "write" in char.properties:
                        properties.append("WRITE")
                    if "write-without-response" in char.properties:
                        properties.append("WRITE_NO_RESP")
                    if "notify" in char.properties:
                        properties.append("NOTIFY")
                    if "indicate" in char.properties:
                        properties.append("INDICATE")
                    
                    _LOGGER.info(
                        "    Characteristic %d/%d: UUID=%s, Properties=[%s], Description='%s'",
                        char_idx,
                        len(service.characteristics),
                        char.uuid,
                        ", ".join(properties),
                        char.description or "No description"
                    )
                    
                    # Try to read characteristic value if readable
                    if "read" in char.properties:
                        try:
                            # Handle Home Assistant's BLE client wrapper for reading
                            value = None
                            try:
                                value = await client.read_gatt_char(char.uuid)
                            except AttributeError:
                                if hasattr(client, '_client'):
                                    value = await client._client.read_gatt_char(char.uuid)
                            
                            if value is not None:
                                if len(value) <= 20:  # Only log small values to avoid spam
                                    _LOGGER.info(
                                        "      Current value: %s (hex: %s)",
                                        value,
                                        value.hex() if value else "empty"
                                    )
                                else:
                                    _LOGGER.info("      Current value: %d bytes (too large to display)", len(value))
                        except Exception as err:
                            _LOGGER.info("      Could not read value: %s", err)
                    
                    # Log descriptors if any
                    if char.descriptors:
                        _LOGGER.info("      Found %d descriptors:", len(char.descriptors))
                        for desc_idx, desc in enumerate(char.descriptors, 1):
                            _LOGGER.info(
                                "        Descriptor %d/%d: UUID=%s, Description='%s'",
                                desc_idx,
                                len(char.descriptors),
                                desc.uuid,
                                desc.description or "No description"
                            )
                            
                            # Try to read descriptor value
                            try:
                                # Handle Home Assistant's BLE client wrapper for descriptor reading
                                desc_value = None
                                try:
                                    desc_value = await client.read_gatt_descriptor(desc.handle)
                                except AttributeError:
                                    if hasattr(client, '_client'):
                                        desc_value = await client._client.read_gatt_descriptor(desc.handle)
                                
                                if desc_value is not None:
                                    if len(desc_value) <= 20:
                                        _LOGGER.info(
                                            "          Value: %s (hex: %s)",
                                            desc_value,
                                            desc_value.hex() if desc_value else "empty"
                                        )
                                    else:
                                        _LOGGER.info("          Value: %d bytes", len(desc_value))
                            except Exception as err:
                                _LOGGER.info("          Could not read descriptor: %s", err)
            else:
                _LOGGER.info("  No characteristics found in service %s", service.uuid)
        
        _LOGGER.info("=== BLE DISCOVERY END for device %s ===", device_address)
        
    except Exception as err:
        _LOGGER.error("Error during BLE discovery for device %s: %s", device_address, err)


class RateLimitedLogger:
    """Rate-limited logger to prevent log spam."""
    
    def __init__(self, logger: logging.Logger, window: int = 60, max_logs: int = 10):
        """Initialize rate-limited logger."""
        self._logger = logger
        self._window = window
        self._max_logs = max_logs
        self._log_times: list[float] = []
    
    def _should_log(self) -> bool:
        """Check if we should log based on rate limiting."""
        now = time.time()
        # Remove old log entries outside the window
        self._log_times = [t for t in self._log_times if now - t < self._window]
        
        if len(self._log_times) < self._max_logs:
            self._log_times.append(now)
            return True
        return False
    
    def debug(self, msg: str, *args: Any) -> None:
        """Log debug message if rate limit allows."""
        if self._should_log():
            self._logger.debug(msg, *args)
    
    def info(self, msg: str, *args: Any) -> None:
        """Log info message if rate limit allows."""
        if self._should_log():
            self._logger.info(msg, *args)
    
    def warning(self, msg: str, *args: Any) -> None:
        """Log warning message if rate limit allows."""
        if self._should_log():
            self._logger.warning(msg, *args)
    
    def error(self, msg: str, *args: Any) -> None:
        """Log error message if rate limit allows."""
        if self._should_log():
            self._logger.error(msg, *args)


class VogelsMotionMountConnection:
    """Manages BLE connection to a Vogels MotionMount device."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        device_address: str,
        adapter: str | None = None,
        uuids: dict[str, str] | None = None,
        auto_disconnect_timeout: int = 0,
        debug_raw_data: bool = False,
    ) -> None:
        """Initialize the connection manager."""
        self._hass = hass
        self._device_address = device_address
        self._adapter = adapter
        self._auto_disconnect_timeout = auto_disconnect_timeout
        self._debug_raw_data = debug_raw_data
        
        # GATT UUIDs
        self._uuids = uuids or {}
        
        # Connection state
        self._client: BleakClient | None = None
        self._connected = False
        self._connecting = False
        self._reconnect_task: asyncio.Task | None = None
        self._disconnect_task: asyncio.Task | None = None
        self._shutdown = False
        
        # Reconnection state
        self._reconnect_attempts = 0
        self._last_activity_time = time.time()
        
        # Data and callbacks
        self._telemetry_data = TelemetryData()
        self._telemetry_callback: Callable[[TelemetryData], None] | None = None
        self._connection_stats = ConnectionStats()

        # Connection state (exposed to entities via a sensor)
        self._connection_state: ConnectionState = ConnectionState.DISCONNECTED
        self._state_callback: Callable[[ConnectionState], None] | None = None

        # Logging
        self._logger = RateLimitedLogger(_LOGGER)

        # Lock for connection operations
        self._connection_lock = asyncio.Lock()
    
    @property
    def is_connected(self) -> bool:
        """Return if the device is connected."""
        if not self._connected or not self._client:
            return False
        
        # Check if the underlying client is still connected
        try:
            return self._client.is_connected
        except Exception:
            # If we can't check connection state, assume disconnected
            self._connected = False
            return False
    
    @property
    def telemetry_data(self) -> TelemetryData:
        """Return current telemetry data."""
        return self._telemetry_data
    
    @property
    def connection_stats(self) -> ConnectionStats:
        """Return connection statistics."""
        self._connection_stats.is_connected = self.is_connected
        self._connection_stats.current_adapter = self._adapter
        return self._connection_stats
    
    def set_telemetry_callback(
        self, callback: Callable[[TelemetryData], None] | None
    ) -> None:
        """Set callback for telemetry updates."""
        self._telemetry_callback = callback

    def set_state_callback(
        self, callback: Callable[[ConnectionState], None] | None
    ) -> None:
        """Set callback invoked whenever the connection state changes."""
        self._state_callback = callback

    @property
    def connection_state(self) -> ConnectionState:
        """Return the current high-level connection state."""
        return self._connection_state

    def _set_connection_state(self, state: ConnectionState) -> None:
        """Update the connection state and notify listeners."""
        if self._connection_state == state:
            return
        self._connection_state = state
        if self._state_callback is not None:
            try:
                self._state_callback(state)
            except Exception as err:  # pylint: disable=broad-except
                self._logger.error("Error in connection-state callback: %s", err)
    
    async def async_connect(self) -> bool:
        """Connect to the device."""
        async with self._connection_lock:
            if self._shutdown:
                return False

            if self.is_connected:
                # Make sure state is in sync with the underlying client.
                self._set_connection_state(ConnectionState.CONNECTED)
                return True

            self._connecting = True
            self._set_connection_state(ConnectionState.CONNECTING)

            try:
                self._connection_stats.connection_attempts += 1

                self._logger.debug(
                    "Connecting to device %s via adapter %s",
                    self._device_address,
                    self._adapter or "default",
                )

                # Get BLE device from HA's Bluetooth integration
                ble_device = async_ble_device_from_address(self._hass, self._device_address)
                if not ble_device:
                    error_msg = f"Device {self._device_address} not found in Bluetooth discovery"
                    self._logger.warning(error_msg)
                    self._connection_stats.last_error = error_msg
                    self._set_connection_state(ConnectionState.ERROR)
                    return False

                # Use bleak-retry-connector for reliable connection
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._device_address,
                    max_attempts=3,
                )

                # Subscribe to telemetry
                await self._subscribe_telemetry()

                self._connected = True
                self._reconnect_attempts = 0
                self._last_activity_time = time.time()
                self._connection_stats.successful_connections += 1
                self._connection_stats.last_error = None
                self._set_connection_state(ConnectionState.CONNECTED)

                self._logger.info("Successfully connected to device %s", self._device_address)

                # Start auto-disconnect timer if configured
                if self._auto_disconnect_timeout > 0:
                    self._schedule_auto_disconnect()

                return True

            except asyncio.TimeoutError:
                error_msg = f"Connection timeout to {self._device_address}"
                self._logger.warning(error_msg)
                self._connection_stats.last_error = error_msg
                self._set_connection_state(ConnectionState.ERROR)
                return False

            except BleakError as err:
                error_msg = f"BLE error connecting to {self._device_address}: {err}"
                self._logger.warning(error_msg)
                self._connection_stats.last_error = error_msg
                self._set_connection_state(ConnectionState.ERROR)
                return False

            except Exception as err:
                error_msg = f"Unexpected error connecting to {self._device_address}: {err}"
                self._logger.error(error_msg)
                self._connection_stats.last_error = error_msg
                self._set_connection_state(ConnectionState.ERROR)
                return False

            finally:
                self._connecting = False
    
    async def async_disconnect(self) -> None:
        """Disconnect from the device.

        The whole operation is bounded by ``_DISCONNECT_TIMEOUT`` so that
        a stuck BLE stack cannot block Home Assistant's reload/unload.
        """
        async with self._connection_lock:
            # Always cancel background timers, even if we weren't "connected".
            if self._disconnect_task and not self._disconnect_task.done():
                self._disconnect_task.cancel()
                self._disconnect_task = None

            if not self._client:
                self._connected = False
                self._set_connection_state(ConnectionState.DISCONNECTED)
                return

            self._logger.debug("Disconnecting from device %s", self._device_address)

            try:
                try:
                    await asyncio.wait_for(
                        self._client.stop_notify(self._uuids.get("nus_tx", "")),
                        timeout=_DISCONNECT_TIMEOUT,
                    )
                except (asyncio.TimeoutError, Exception) as err:
                    self._logger.debug("Error stopping notifications: %s", err)

                try:
                    await asyncio.wait_for(
                        self._client.disconnect(),
                        timeout=_DISCONNECT_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    self._logger.warning(
                        "Disconnect from %s timed out after %.0fs; forcing state to disconnected",
                        self._device_address,
                        _DISCONNECT_TIMEOUT,
                    )
                except Exception as err:  # pylint: disable=broad-except
                    self._logger.debug("Error during disconnect: %s", err)
            finally:
                self._connected = False
                self._connection_stats.disconnections += 1
                self._set_connection_state(ConnectionState.DISCONNECTED)
                self._logger.debug("Disconnected from device %s", self._device_address)

    async def async_shutdown(self) -> None:
        """Shutdown the connection manager.

        Bounded so that an unresponsive BLE stack cannot keep Home
        Assistant from unloading or reloading the config entry (which
        is what previously caused the options flow to hang / crash HA).
        """
        self._shutdown = True

        for task in (self._reconnect_task, self._disconnect_task):
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as err:  # pylint: disable=broad-except
                    self._logger.debug("Error awaiting cancelled task: %s", err)

        self._reconnect_task = None
        self._disconnect_task = None

        try:
            await asyncio.wait_for(
                self.async_disconnect(), timeout=_DISCONNECT_TIMEOUT + 1.0
            )
        except asyncio.TimeoutError:
            self._logger.warning(
                "Shutdown disconnect for %s exceeded bounded timeout; continuing",
                self._device_address,
            )
            # Force-clear state so callers see a clean disconnected status.
            self._connected = False
            self._client = None
            self._set_connection_state(ConnectionState.DISCONNECTED)
    
    async def _force_disconnect_for_retry(self) -> None:
        """Tear down a stale client so the next attempt builds from scratch."""
        try:
            if self._client is not None:
                try:
                    await asyncio.wait_for(
                        self._client.disconnect(), timeout=_DISCONNECT_TIMEOUT
                    )
                except (asyncio.TimeoutError, Exception) as err:  # pylint: disable=broad-except
                    self._logger.debug(
                        "Forced disconnect error for %s: %s",
                        self._device_address,
                        err,
                    )
        finally:
            self._client = None
            self._connected = False

    async def _write_characteristic(
        self,
        characteristic: str,
        data: bytes,
        label: str,
    ) -> bool:
        """Ensure the connection is alive, then write to the characteristic.

        Tries twice: the first attempt may fail if the cached BLE
        connection went stale during idle — in that case we tear the
        client down and reconnect from scratch before retrying.
        """
        uuid = self._uuids.get(characteristic)
        if not uuid:
            self._logger.error("UUID for %s not configured", characteristic)
            return False

        last_err: str | None = None
        for attempt in range(1, 3):
            if not self.is_connected:
                self._logger.info(
                    "%s: device not connected, connecting (attempt %d/2)",
                    label,
                    attempt,
                )
                if not await self.async_connect():
                    last_err = "connect failed"
                    continue

            try:
                self._last_activity_time = time.time()
                self._logger.debug(
                    "%s: writing %s (%d bytes) to %s",
                    label,
                    data.hex(),
                    len(data),
                    uuid,
                )
                await asyncio.wait_for(
                    self._client.write_gatt_char(uuid, data, response=True),
                    timeout=_WRITE_TIMEOUT,
                )
                return True
            except asyncio.TimeoutError:
                last_err = "timeout"
                self._logger.warning(
                    "%s: write timed out (attempt %d/2)", label, attempt
                )
            except BleakError as err:
                last_err = f"BLE error: {err}"
                self._logger.warning(
                    "%s: BLE error on write (attempt %d/2): %s", label, attempt, err
                )
            except Exception as err:  # pylint: disable=broad-except
                last_err = f"error: {err}"
                self._logger.error(
                    "%s: unexpected error on write (attempt %d/2): %s",
                    label,
                    attempt,
                    err,
                )

            # Tear down the stale client so the next loop iteration
            # establishes a completely fresh connection.
            await self._force_disconnect_for_retry()

        self._logger.error("%s: giving up after 2 attempts (%s)", label, last_err)
        return False

    async def async_write_target(self, characteristic: str, value: int) -> bool:
        """Write a target value to a characteristic."""
        # Extension is unsigned (0 at wall .. 100 fully extended).
        # Turn is signed. The UI uses slider-intuitive signs
        # (-100 = left, +100 = right) but the device firmware uses
        # the opposite convention, so we invert for the wire.
        # Both are packed as signed int16 little-endian.
        if characteristic == "turn_target":
            clamped = max(-100, min(100, int(value)))
            wire_value = -clamped
        else:
            clamped = max(0, min(100, int(value)))
            wire_value = clamped
        data = struct.pack("<h", wire_value)

        return await self._write_characteristic(
            characteristic,
            data,
            label=f"{characteristic}={clamped} (wire={wire_value})",
        )

    async def async_write_preset(self, preset_index: int) -> bool:
        """Write a preset index."""
        # Per device docs: single byte index.
        data = bytes([max(0, min(255, int(preset_index)))])
        return await self._write_characteristic(
            "preset",
            data,
            label=f"preset {preset_index}",
        )
    
    async def _subscribe_telemetry(self) -> None:
        """Subscribe to telemetry notifications."""
        if not self._client or not self._client.is_connected:
            return
        
        uuid = self._uuids.get("nus_tx")
        if not uuid:
            self._logger.error("NUS TX UUID not configured")
            return
        
        try:
            await self._client.start_notify(uuid, self._handle_telemetry)
            self._logger.debug("Subscribed to telemetry notifications")
        except Exception as err:
            self._logger.error("Failed to subscribe to telemetry: %s", err)
            raise
    
    def _handle_telemetry(self, sender: Any, data: bytearray) -> None:
        """Handle incoming telemetry data."""
        try:
            line = data.decode("ascii", errors="ignore").strip()
            self._logger.info("Received telemetry: %s", line)
            if self._debug_raw_data:
                self._logger.debug("Raw telemetry: %s", repr(data))
            
            self._connection_stats.telemetry_lines_received += 1
            self._connection_stats.last_telemetry_time = time.time()
            self._last_activity_time = time.time()  # Update activity time
            
            recognized, changed = self._telemetry_data.update_from_line(line)

            if not recognized:
                self._logger.warning("Telemetry line did not match expected format: %s", line)
                return

            if changed:
                self._logger.info(
                    "Telemetry data updated: ext=%s, turn=%s, ext_target=%s, turn_target=%s, moving=%s",
                    self._telemetry_data.extension_current,
                    self._telemetry_data.turn_current,
                    self._telemetry_data.extension_target,
                    self._telemetry_data.turn_target,
                    self._telemetry_data.is_moving,
                )
                if self._telemetry_callback:
                    try:
                        self._telemetry_callback(self._telemetry_data)
                    except Exception as err:
                        self._logger.error("Error in telemetry callback: %s", err)
                
        except Exception as err:
            self._logger.error("Error handling telemetry data: %s", err)
    
    def _schedule_auto_disconnect(self) -> None:
        """Schedule automatic disconnect after idle timeout."""
        if self._disconnect_task and not self._disconnect_task.done():
            self._disconnect_task.cancel()
        
        self._disconnect_task = asyncio.create_task(self._auto_disconnect_timer())
    
    async def _auto_disconnect_timer(self) -> None:
        """Auto-disconnect timer task."""
        try:
            while not self._shutdown and self.is_connected:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if time.time() - self._last_activity_time > self._auto_disconnect_timeout:
                    self._logger.info(
                        "Auto-disconnecting after %d seconds of inactivity",
                        self._auto_disconnect_timeout
                    )
                    await self.async_disconnect()
                    break
                    
        except asyncio.CancelledError:
            pass
        except Exception as err:
            self._logger.error("Error in auto-disconnect timer: %s", err)
    
    async def _reconnect_with_backoff(self) -> None:
        """Reconnect with exponential backoff."""
        while not self._shutdown and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            # Calculate delay with exponential backoff and jitter
            delay = min(
                RECONNECT_BASE_DELAY * (2 ** self._reconnect_attempts),
                RECONNECT_MAX_DELAY
            )
            jitter = random.uniform(0, min(RECONNECT_JITTER_MAX, delay * 0.1))
            total_delay = delay + jitter
            
            self._logger.debug(
                "Reconnect attempt %d/%d in %.1f seconds",
                self._reconnect_attempts + 1,
                MAX_RECONNECT_ATTEMPTS,
                total_delay
            )
            
            await asyncio.sleep(total_delay)
            
            if await self.async_connect():
                self._logger.info("Reconnection successful")
                return
            
            self._reconnect_attempts += 1
        
        if not self._shutdown:
            self._logger.error(
                "Failed to reconnect after %d attempts",
                MAX_RECONNECT_ATTEMPTS
            )
    
    def schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._shutdown or self._reconnect_task and not self._reconnect_task.done():
            return
        
        self._reconnect_task = asyncio.create_task(self._reconnect_with_backoff())
