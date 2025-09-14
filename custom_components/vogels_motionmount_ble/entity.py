"""Base entity for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VogelsMotionMountCoordinator

_LOGGER = logging.getLogger(__name__)


class VogelsMotionMountEntity(CoordinatorEntity[VogelsMotionMountCoordinator]):
    """Base entity for Vogels MotionMount BLE."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        self._attr_unique_id = f"{coordinator.device_address}_{entity_key}"
        self._entity_key = entity_key

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_address)},
            name=self.coordinator.device_name,
            manufacturer="Vogels",
            model="MotionMount",
            sw_version="1.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # In on-demand mode, entities are always available
        return True
