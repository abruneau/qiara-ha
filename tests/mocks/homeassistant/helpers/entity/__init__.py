from enum import Enum
from typing import Any

class EntityCategory(str, Enum):
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"

class Entity:
    _attr_name: str | None = None
    _attr_unique_id: str | None = None
    _attr_device_class: str | None = None
    _attr_icon: str | None = None
    _attr_unit_of_measurement: str | None = None
    _attr_available: bool = True

    @property
    def name(self) -> str | None:
        return self._attr_name

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def device_class(self) -> str | None:
        return self._attr_device_class

    @property
    def available(self) -> bool:
        return self._attr_available
