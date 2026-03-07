from enum import Enum
from typing import Any
from homeassistant.helpers.entity import Entity

class SensorDeviceClass(str, Enum):
    BATTERY = "battery"
class SensorStateClass(str, Enum):
    MEASUREMENT = "measurement"

class SensorEntity(Entity):
    _attr_native_value: Any = None
    _attr_native_unit_of_measurement: str | None = None
    _attr_state_class: str | None = None

    @property
    def native_value(self) -> Any:
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._attr_native_unit_of_measurement
