"""Number entities for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_EXTENSION_TARGET,
    ENTITY_TURN_TARGET,
    MAX_TARGET_VALUE,
    MIN_TARGET_VALUE,
)
from .coordinator import VogelsMotionMountCoordinator
from .entity import VogelsMotionMountEntity
from .models import VogelsMotionMountData

_LOGGER = logging.getLogger(__name__)

NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=ENTITY_EXTENSION_TARGET,
        name="Extension Target",
        icon="mdi:arrow-expand-horizontal",
        native_min_value=MIN_TARGET_VALUE,
        native_max_value=MAX_TARGET_VALUE,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    NumberEntityDescription(
        key=ENTITY_TURN_TARGET,
        name="Turn Target", 
        icon="mdi:rotate-3d-variant",
        native_min_value=MIN_TARGET_VALUE,
        native_max_value=MAX_TARGET_VALUE,
        native_step=1,
        native_unit_of_measurement="%",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    data: VogelsMotionMountData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    entities = [
        VogelsMotionMountNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]

    async_add_entities(entities)


class VogelsMotionMountNumber(VogelsMotionMountEntity, NumberEntity):
    """Number entity for Vogels MotionMount targets."""

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
            
        if self.entity_description.key == ENTITY_EXTENSION_TARGET:
            # For target entities, we don't have a "current target" from telemetry
            # Return None to indicate unknown state
            return None
        elif self.entity_description.key == ENTITY_TURN_TARGET:
            return None
        
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the target value."""
        int_value = int(value)
        
        _LOGGER.debug(
            "Setting %s to %d for %s",
            self.entity_description.key,
            int_value,
            self.coordinator.device_name,
        )
        
        success = False
        if self.entity_description.key == ENTITY_EXTENSION_TARGET:
            success = await self.coordinator.async_write_extension_target(int_value)
        elif self.entity_description.key == ENTITY_TURN_TARGET:
            success = await self.coordinator.async_write_turn_target(int_value)
        
        if not success:
            _LOGGER.error(
                "Failed to set %s to %d for %s",
                self.entity_description.key,
                int_value,
                self.coordinator.device_name,
            )
