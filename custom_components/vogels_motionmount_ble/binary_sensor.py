"""Binary sensor entities for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_IS_MOVING,
)
from .coordinator import VogelsMotionMountCoordinator
from .entity import VogelsMotionMountEntity
from .models import VogelsMotionMountData

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=ENTITY_IS_MOVING,
        name="Is Moving",
        icon="mdi:motion",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    data: VogelsMotionMountData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    entities = [
        VogelsMotionMountBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class VogelsMotionMountBinarySensor(VogelsMotionMountEntity, BinarySensorEntity):
    """Binary sensor entity for Vogels MotionMount moving state."""

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the mount is moving."""
        if not self.coordinator.data:
            return None
            
        if self.entity_description.key == ENTITY_IS_MOVING:
            return self.coordinator.data.is_moving
        
        return None
