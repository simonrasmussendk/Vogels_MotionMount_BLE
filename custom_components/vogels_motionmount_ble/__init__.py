"""The Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import VogelsMotionMountCoordinator
from .models import VogelsMotionMountData

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vogels MotionMount BLE from a config entry."""
    _LOGGER.info("Setting up Vogels MotionMount BLE entry: %s", entry.title)
    
    coordinator = VogelsMotionMountCoordinator(hass, entry)
    
    try:
        await coordinator.async_setup()
    except Exception as err:
        _LOGGER.error("Failed to set up Vogels MotionMount BLE: %s", err)
        raise ConfigEntryNotReady from err
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = VogelsMotionMountData(
        coordinator=coordinator,
    )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Vogels MotionMount BLE entry: %s", entry.title)
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: VogelsMotionMountData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.coordinator.async_shutdown()
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
