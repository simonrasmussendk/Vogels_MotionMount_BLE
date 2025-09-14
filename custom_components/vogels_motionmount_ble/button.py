"""Button entities for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_PRESET_0,
    ENTITY_PRESET_1,
    ENTITY_PRESET_2,
    ENTITY_PRESET_3,
    ENTITY_PRESET_4,
    ENTITY_PRESET_5,
    ENTITY_PRESET_6,
    ENTITY_STOP,
)
from .coordinator import VogelsMotionMountCoordinator
from .entity import VogelsMotionMountEntity
from .models import VogelsMotionMountData

_LOGGER = logging.getLogger(__name__)

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key=ENTITY_PRESET_0,
        name="Preset 0",
        icon="mdi:numeric-0-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_1,
        name="Preset 1",
        icon="mdi:numeric-1-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_2,
        name="Preset 2",
        icon="mdi:numeric-2-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_3,
        name="Preset 3",
        icon="mdi:numeric-3-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_4,
        name="Preset 4",
        icon="mdi:numeric-4-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_5,
        name="Preset 5",
        icon="mdi:numeric-5-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_PRESET_6,
        name="Preset 6",
        icon="mdi:numeric-6-circle",
    ),
    ButtonEntityDescription(
        key=ENTITY_STOP,
        name="Stop",
        icon="mdi:stop",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    data: VogelsMotionMountData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    entities = [
        VogelsMotionMountButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]

    async_add_entities(entities)


class VogelsMotionMountButton(VogelsMotionMountEntity, ButtonEntity):
    """Button entity for Vogels MotionMount presets and stop."""

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info(
            "Button %s pressed for %s (available: %s)",
            self.entity_description.key,
            self.coordinator.device_name,
            self.available,
        )
        
        success = False
        
        if self.entity_description.key == ENTITY_PRESET_0:
            _LOGGER.info("Executing preset 0")
            success = await self.coordinator.async_write_preset(0)
        elif self.entity_description.key == ENTITY_PRESET_1:
            _LOGGER.info("Executing preset 1")
            success = await self.coordinator.async_write_preset(1)
        elif self.entity_description.key == ENTITY_PRESET_2:
            _LOGGER.info("Executing preset 2")
            success = await self.coordinator.async_write_preset(2)
        elif self.entity_description.key == ENTITY_PRESET_3:
            _LOGGER.info("Executing preset 3")
            success = await self.coordinator.async_write_preset(3)
        elif self.entity_description.key == ENTITY_PRESET_4:
            _LOGGER.info("Executing preset 4")
            success = await self.coordinator.async_write_preset(4)
        elif self.entity_description.key == ENTITY_PRESET_5:
            _LOGGER.info("Executing preset 5")
            success = await self.coordinator.async_write_preset(5)
        elif self.entity_description.key == ENTITY_PRESET_6:
            _LOGGER.info("Executing preset 6")
            success = await self.coordinator.async_write_preset(6)
        elif self.entity_description.key == ENTITY_STOP:
            _LOGGER.info("Executing stop command")
            success = await self.coordinator.async_stop_movement()
        
        if success:
            _LOGGER.info(
                "Successfully executed button %s for %s",
                self.entity_description.key,
                self.coordinator.device_name,
            )
        else:
            _LOGGER.error(
                "Failed to execute button %s for %s",
                self.entity_description.key,
                self.coordinator.device_name,
            )
