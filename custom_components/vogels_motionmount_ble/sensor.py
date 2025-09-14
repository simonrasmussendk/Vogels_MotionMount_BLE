"""Sensor entities for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_EXTENSION_CURRENT,
    ENTITY_TURN_CURRENT,
)
from .coordinator import VogelsMotionMountCoordinator
from .entity import VogelsMotionMountEntity
from .models import VogelsMotionMountData

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ENTITY_EXTENSION_CURRENT,
        name="Extension Current",
        icon="mdi:arrow-expand-horizontal",
        native_unit_of_measurement="%",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key=ENTITY_TURN_CURRENT,
        name="Turn Current",
        icon="mdi:rotate-3d-variant", 
        native_unit_of_measurement="%",
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    data: VogelsMotionMountData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    entities = [
        VogelsMotionMountSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class VogelsMotionMountSensor(VogelsMotionMountEntity, SensorEntity):
    """Sensor entity for Vogels MotionMount current values."""

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
            
        if self.entity_description.key == ENTITY_EXTENSION_CURRENT:
            return self.coordinator.data.extension_current
        elif self.entity_description.key == ENTITY_TURN_CURRENT:
            return self.coordinator.data.turn_current
        
        return None
