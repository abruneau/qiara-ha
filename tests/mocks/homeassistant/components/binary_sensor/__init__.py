from enum import Enum
from homeassistant.helpers.entity import Entity

class BinarySensorDeviceClass(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    MOTION = "motion"
    SMOKE = "smoke"
    CO = "co"

class BinarySensorEntity(Entity):
    _attr_is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        return self._attr_is_on
