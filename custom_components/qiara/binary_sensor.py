"""Support for Qiara binary sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .models import QiaraSensorData

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES = {
    "door": BinarySensorDeviceClass.DOOR,
    "window": BinarySensorDeviceClass.WINDOW,
    "motion": BinarySensorDeviceClass.MOTION,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "co": BinarySensorDeviceClass.CO,
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qiara binary sensors from a config entry."""
    coordinator: QiaraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for sensor_id, sensor_data in coordinator.data.items():
        if sensor_data.type in BINARY_SENSOR_TYPES:
            entities.append(QiaraBinarySensor(coordinator, entry, sensor_id))

    async_add_entities(entities)


class QiaraBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Qiara binary sensor."""

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}_binary"
        
        sensor_data = coordinator.data[sensor_id]
        self._attr_name = f"{sensor_data.name}"
        self._attr_device_class = BINARY_SENSOR_TYPES.get(sensor_data.type)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{sensor_id}")},
            "name": sensor_data.name,
            "manufacturer": "Qiara",
            "model": sensor_data.type.capitalize(),
            "via_device": (DOMAIN, entry.entry_id),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        if not sensor_data:
            return None
        # Assuming 'open', 'detected', 'alarm' are 'on' states
        return sensor_data.state.lower() in ["open", "detected", "alarm", "on", "true"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        if not sensor_data:
            return {}
        return {
            "battery_level": sensor_data.battery_level,
            "last_triggered": sensor_data.last_updated,
        }

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        return super().available and sensor_data and sensor_data.available
