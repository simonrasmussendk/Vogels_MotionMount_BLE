"""Config flow for Vogels MotionMount BLE integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData, BLEDevice
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

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
    DEFAULT_DEVICE_NAME,
    DEFAULT_LOG_LEVEL,
    DOMAIN,
)
from .connection import discover_device_services, auto_discover_uuids

_LOGGER = logging.getLogger(__name__)


class VogelsMotionMountConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vogels MotionMount BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._adapter: str | None = None
        self._device_address: str | None = None
        self._device_name: str | None = None
        self._discovered_devices: dict[str, BLEDevice] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - select Bluetooth adapter."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._adapter = user_input[CONF_ADAPTER]
            return await self.async_step_device()

        # Get available Bluetooth adapters
        adapters = await self._get_bluetooth_adapters()
        
        if not adapters:
            return self.async_abort(reason="no_bluetooth_adapter")

        data_schema = vol.Schema({
            vol.Required(CONF_ADAPTER): vol.In(adapters)
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "adapter_count": str(len(adapters))
            }
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection and validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._device_address = user_input[CONF_DEVICE_ADDRESS]
            self._device_name = user_input[CONF_DEVICE_NAME]

            # Validate the device and get auto-discovered UUIDs
            try:
                auto_discovered_uuids = await self._validate_device()
                
                # Use auto-discovered UUIDs if available, otherwise fall back to defaults
                config_data = {
                    CONF_ADAPTER: self._adapter,
                    CONF_DEVICE_ADDRESS: self._device_address,
                    CONF_DEVICE_NAME: self._device_name,
                    CONF_AUTO_DISCONNECT_TIMEOUT: DEFAULT_AUTO_DISCONNECT_TIMEOUT,
                    CONF_LOG_LEVEL: DEFAULT_LOG_LEVEL,
                    CONF_DEBUG_RAW_DATA: False,
                    CONF_UUID_NUS_TX: auto_discovered_uuids.get("nus_tx"),
                    CONF_UUID_EXTENSION_TARGET: auto_discovered_uuids.get("extension_target"),
                    CONF_UUID_TURN_TARGET: auto_discovered_uuids.get("turn_target"),
                    CONF_UUID_PRESET: auto_discovered_uuids.get("preset"),
                }
                
                _LOGGER.info("Creating config entry with UUIDs: NUS_TX=%s, EXT=%s, TURN=%s, PRESET=%s",
                            config_data[CONF_UUID_NUS_TX],
                            config_data[CONF_UUID_EXTENSION_TARGET], 
                            config_data[CONF_UUID_TURN_TARGET],
                            config_data[CONF_UUID_PRESET])
                
                return self.async_create_entry(title=self._device_name, data=config_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidDevice:
                errors["base"] = "invalid_device"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during device validation")
                errors["base"] = "unknown"

        # Discover nearby devices
        discovered = await self._discover_devices()
        device_options = {}
        
        for address, device in discovered.items():
            name = device.name or "Unknown Device"
            device_options[address] = f"{name} ({address})"

        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_ADDRESS): vol.In(device_options) if device_options else str,
            vol.Required(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
        })

        return self.async_show_form(
            step_id="device",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "adapter": self._adapter or "Unknown",
                "device_count": str(len(discovered))
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> VogelsMotionMountOptionsFlow:
        """Create the options flow."""
        return VogelsMotionMountOptionsFlow(config_entry)

    async def _get_bluetooth_adapters(self) -> dict[str, str]:
        """Get available Bluetooth adapters."""
        adapters = {}
        
        try:
            # Try to get adapters through Home Assistant's Bluetooth integration
            try:
                bluetooth_adapters = bluetooth.async_discovered_service_info(self.hass)
                # Get unique adapters from discovered services
                adapter_set = set()
                for service_info in bluetooth_adapters:
                    if hasattr(service_info, 'adapter') and service_info.adapter:
                        adapter_set.add(service_info.adapter)
                
                for adapter in sorted(adapter_set):
                    adapters[adapter] = f"Adapter {adapter}"
                    
            except Exception:
                # Fallback: try to get adapters from bluetooth domain data
                try:
                    bluetooth_data = self.hass.data.get("bluetooth", {})
                    if "adapters" in bluetooth_data:
                        for adapter in bluetooth_data["adapters"]:
                            adapters[adapter] = f"Adapter {adapter}"
                except Exception:
                    pass
            
            # Fallback: try to get adapters directly from Bleak
            if not adapters:
                try:
                    from bleak.backends.bluezdbus.manager import get_global_bluez_manager
                    manager = await get_global_bluez_manager()
                    for adapter_path in manager._adapters:
                        adapter_name = adapter_path.split("/")[-1]
                        adapters[adapter_name] = f"Adapter {adapter_name}"
                except Exception:
                    # On non-Linux systems or if BlueZ is not available
                    adapters["default"] = "Default Adapter"
                    
        except Exception as err:
            _LOGGER.warning("Failed to enumerate Bluetooth adapters: %s", err)
            adapters["default"] = "Default Adapter"
        
        return adapters

    async def _discover_devices(self) -> dict[str, BLEDevice]:
        """Discover nearby BLE devices."""
        devices = {}
        
        try:
            scanner = BleakScanner(adapter=self._adapter)
            discovered = await scanner.discover(timeout=10.0)
            
            for device in discovered:
                if device.address:
                    devices[device.address] = device
                    
        except Exception as err:
            _LOGGER.warning("Failed to discover devices: %s", err)
        
        return devices

    async def _validate_device(self) -> dict[str, str]:
        """Validate that the device is a Vogels MotionMount and return auto-discovered UUIDs."""
        if not self._device_address:
            raise InvalidDevice("No device address provided")

        try:
            # Use Home Assistant's Bluetooth integration for connection
            from homeassistant.components.bluetooth import async_ble_device_from_address
            from bleak_retry_connector import establish_connection
            
            # Get BLE device info from HA's Bluetooth integration
            ble_device = async_ble_device_from_address(self.hass, self._device_address)
            if not ble_device:
                raise CannotConnect("Device not found in Bluetooth discovery")
            
            # Use bleak-retry-connector for reliable connection
            client = await establish_connection(
                BleakClient,
                ble_device,
                self._device_address,
                max_attempts=3,
            )
            
            connected = False
            try:
                connected = True
                
                # Perform comprehensive BLE discovery and logging
                _LOGGER.info("Performing BLE discovery for device %s", self._device_address)
                await discover_device_services(client, self._device_address)
                
                # Auto-discover UUIDs based on characteristic properties
                _LOGGER.info("Performing auto-discovery of UUIDs for device %s", self._device_address)
                auto_discovered_uuids = await auto_discover_uuids(client, self._device_address)
                
                # Validate that we found the minimum required characteristics
                required_characteristics = ["nus_tx", "extension_target", "preset"]
                missing_characteristics = [char for char in required_characteristics 
                                         if char not in auto_discovered_uuids]
                
                if missing_characteristics:
                    _LOGGER.error(
                        "Device missing required characteristics: %s. Found: %s", 
                        missing_characteristics, list(auto_discovered_uuids.keys())
                    )
                    raise InvalidDevice(f"Missing required characteristics: {missing_characteristics}")
                
                _LOGGER.info("Device validation successful. Auto-discovered UUIDs: %s", 
                           {k: v for k, v in auto_discovered_uuids.items()})
                
                # Try to subscribe to telemetry briefly using auto-discovered UUID
                if "nus_tx" in auto_discovered_uuids:
                    try:
                        def notification_handler(sender, data):
                            pass
                        
                        await client.start_notify(auto_discovered_uuids["nus_tx"], notification_handler)
                        await asyncio.sleep(2.0)  # Wait for a couple of telemetry messages
                        await client.stop_notify(auto_discovered_uuids["nus_tx"])
                        
                    except Exception as err:
                        _LOGGER.warning("Could not test telemetry subscription: %s", err)
                        # Don't fail validation for this - device might still work
                
                return auto_discovered_uuids
                
            except asyncio.TimeoutError:
                raise CannotConnect("Connection timeout")
            except Exception as err:
                _LOGGER.error("Connection failed: %s", err)
                raise CannotConnect(f"Connection failed: {err}")
            finally:
                if connected:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                        
        except CannotConnect:
            raise
        except InvalidDevice:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error during validation")
            raise CannotConnect(f"Unexpected error: {err}")


class VogelsMotionMountOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Vogels MotionMount BLE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                CONF_AUTO_DISCONNECT_TIMEOUT,
                default=self.config_entry.options.get(
                    CONF_AUTO_DISCONNECT_TIMEOUT, DEFAULT_AUTO_DISCONNECT_TIMEOUT
                )
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
            vol.Optional(
                CONF_LOG_LEVEL,
                default=self.config_entry.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)
            ): vol.In(["DEBUG", "INFO", "WARNING", "ERROR"]),
            vol.Optional(
                CONF_DEBUG_RAW_DATA,
                default=self.config_entry.options.get(CONF_DEBUG_RAW_DATA, False)
            ): bool,
            vol.Optional(
                CONF_UUID_NUS_TX,
                default=self.config_entry.options.get(CONF_UUID_NUS_TX, self.config_entry.data.get(CONF_UUID_NUS_TX))
            ): str,
            vol.Optional(
                CONF_UUID_EXTENSION_TARGET,
                default=self.config_entry.options.get(
                    CONF_UUID_EXTENSION_TARGET, self.config_entry.data.get(CONF_UUID_EXTENSION_TARGET)
                )
            ): str,
            vol.Optional(
                CONF_UUID_TURN_TARGET,
                default=self.config_entry.options.get(
                    CONF_UUID_TURN_TARGET, self.config_entry.data.get(CONF_UUID_TURN_TARGET)
                )
            ): str,
            vol.Optional(
                CONF_UUID_PRESET,
                default=self.config_entry.options.get(CONF_UUID_PRESET, self.config_entry.data.get(CONF_UUID_PRESET))
            ): str,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidDevice(HomeAssistantError):
    """Error to indicate the device is not a valid Vogels MotionMount."""
