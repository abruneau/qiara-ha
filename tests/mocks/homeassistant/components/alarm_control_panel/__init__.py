from enum import Enum, IntFlag
from homeassistant.helpers.entity import Entity


class AlarmControlPanelState(str, Enum):
    DISARMED = "disarmed"
    ARMED_HOME = "armed_home"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"
    ARMED_VACATION = "armed_vacation"
    ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
    PENDING = "pending"
    ARMING = "arming"
    DISARMING = "disarming"
    TRIGGERED = "triggered"


class AlarmControlPanelEntityFeature(IntFlag):
    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    ARM_VACATION = 8
    TRIGGER = 16
    ARM_CUSTOM_BYPASS = 32


class AlarmControlPanelEntity(Entity):
    _attr_alarm_state: AlarmControlPanelState | None = None
    _attr_supported_features: AlarmControlPanelEntityFeature = AlarmControlPanelEntityFeature(0)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        return self._attr_alarm_state

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        return self._attr_supported_features

    def async_write_ha_state(self) -> None:
        """Mock state write."""
        pass

    async def async_alarm_disarm(self, code=None) -> None:
        raise NotImplementedError

    async def async_alarm_arm_home(self, code=None) -> None:
        raise NotImplementedError

    async def async_alarm_arm_night(self, code=None) -> None:
        raise NotImplementedError
