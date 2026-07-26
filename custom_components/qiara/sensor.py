"""Support for Qiara diagnostic sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .models import QiaraSensorData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qiara diagnostic sensors from a config entry."""
    coordinator: QiaraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    temperature_unique_ids: set[str] = set()
    for sensor_id, sensor_data in coordinator.data.items():
        if not isinstance(sensor_data, QiaraSensorData):
            continue
        if sensor_data.battery_level is not None:
            entities.append(QiaraBatterySensor(coordinator, entry, sensor_id))
        if sensor_data.temperature is not None:
            entities.append(QiaraTemperatureSensor(coordinator, entry, sensor_id))
            temperature_unique_ids.add(f"{entry.entry_id}_{sensor_id}_temperature")

    # Drop any temperature entity for a node that no longer reports a
    # temperature. Nodes without a real reading (door/window, motion, keypad)
    # only ever return the sentinel value 200, which older versions exposed as
    # ~20 °C. Those entities now linger in the registry as "unavailable"
    # restored entities, so remove them instead of leaving them orphaned.
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if (
            reg_entry.domain == "sensor"
            and reg_entry.unique_id.endswith("_temperature")
            and reg_entry.unique_id not in temperature_unique_ids
        ):
            ent_reg.async_remove(reg_entry.entity_id)

    async_add_entities(entities)


class QiaraBatterySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Qiara battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}_battery"
        
        sensor_data = coordinator.data[sensor_id]
        self._attr_name = f"{sensor_data.name} Battery"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{sensor_id}")},
            "name": sensor_data.name,
            "manufacturer": "Qiara",
            "model": sensor_data.type.capitalize(),
            "via_device": (DOMAIN, entry.entry_id),
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        if not sensor_data:
            return None
        return sensor_data.battery_level

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        return super().available and sensor_data and sensor_data.available


class QiaraTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Qiara temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}_temperature"

        sensor_data = coordinator.data[sensor_id]
        self._attr_name = f"{sensor_data.name} Temperature"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{sensor_id}")},
            "name": sensor_data.name,
            "manufacturer": "Qiara",
            "model": sensor_data.type.capitalize(),
            "via_device": (DOMAIN, entry.entry_id),
        }

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        if not sensor_data:
            return None
        return sensor_data.temperature

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        sensor_data: QiaraSensorData = self.coordinator.data.get(self._sensor_id)
        return super().available and sensor_data and sensor_data.available
