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
        if not isinstance(sensor_data, QiaraSensorData):
            continue
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
        }
        if coordinator.hub_device_id:
            self._attr_device_info["via_device_id"] = coordinator.hub_device_id

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on (open / motion detected).

        The device reports an inactive sensor as ``False`` (and sometimes
        ``None``), and an active one as a truthy value — ``True`` from an
        endpoint read, or a state string like ``"dws_open"``/``"mvt_detected"``
        from a push event. So treat any truthy value as "on"; ``False``/``None``
        must read as "off" (a plain ``is not None`` check wrongly reported
        every idle sensor as detected).
        """
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        if not sensor_data:
            return None
        return bool(sensor_data.state)

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
        return bool(super().available and sensor_data and sensor_data.available)
