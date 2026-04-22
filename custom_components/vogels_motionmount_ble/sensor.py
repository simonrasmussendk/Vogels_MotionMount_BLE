"""Sensor entities for Vogels MotionMount BLE integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_CONNECTION_STATUS,
    ENTITY_EXTENSION_CURRENT,
    ENTITY_TURN_CURRENT,
)
from .coordinator import VogelsMotionMountCoordinator
from .entity import VogelsMotionMountEntity
from .models import ConnectionState, VogelsMotionMountData

_LOGGER = logging.getLogger(__name__)

CONNECTION_STATE_VALUES: list[str] = [state.value for state in ConnectionState]

# Per-state icon mapping for the connection status sensor.
_CONNECTION_STATE_ICONS: dict[ConnectionState, str] = {
    ConnectionState.DISCONNECTED: "mdi:bluetooth-off",
    ConnectionState.CONNECTING: "mdi:bluetooth-transfer",
    ConnectionState.CONNECTED: "mdi:bluetooth-connect",
    ConnectionState.ERROR: "mdi:bluetooth-alert",
}

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
    SensorEntityDescription(
        key=ENTITY_CONNECTION_STATUS,
        name="Connection Status",
        icon="mdi:bluetooth",
        device_class=SensorDeviceClass.ENUM,
        options=CONNECTION_STATE_VALUES,
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

    entities: list[SensorEntity] = []
    for description in SENSOR_DESCRIPTIONS:
        if description.key == ENTITY_CONNECTION_STATUS:
            entities.append(VogelsMotionMountConnectionSensor(coordinator, description))
        else:
            entities.append(VogelsMotionMountSensor(coordinator, description))

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
        if self.entity_description.key == ENTITY_TURN_CURRENT:
            return self.coordinator.data.turn_current

        return None


class VogelsMotionMountConnectionSensor(VogelsMotionMountEntity, SensorEntity):
    """Sensor entity exposing the current BLE connection state."""

    def __init__(
        self,
        coordinator: VogelsMotionMountCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the connection-status sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str:
        """Return the current connection state as a string."""
        return self.coordinator.connection_state.value

    @property
    def icon(self) -> str:
        """Return an icon that reflects the current state."""
        return _CONNECTION_STATE_ICONS.get(
            self.coordinator.connection_state, "mdi:bluetooth"
        )
