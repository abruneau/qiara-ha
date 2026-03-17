"""Support for Qiara alarm control panel."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SYSTEM_MODE_DAY, SYSTEM_MODE_NIGHT
from .coordinator import QiaraDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qiara alarm control panel from a config entry."""
    coordinator: QiaraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([QiaraAlarmControlPanel(coordinator, entry)])


class QiaraAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of the Qiara alarm control panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required: bool = False

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_alarm_control_panel"
        self._attr_name = "Qiara Alarm"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Qiara Security System",
            manufacturer="Qiara",
        )
        self._optimistic_state: AlarmControlPanelState = AlarmControlPanelState.DISARMED

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the current alarm state."""
        return self._optimistic_state

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm in home (day) mode."""
        try:
            await self.coordinator.api.async_arm_system(SYSTEM_MODE_DAY)
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        self._optimistic_state = AlarmControlPanelState.ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm in night mode."""
        try:
            await self.coordinator.api.async_arm_system(SYSTEM_MODE_NIGHT)
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        self._optimistic_state = AlarmControlPanelState.ARMED_NIGHT
        self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm system."""
        try:
            await self.coordinator.api.async_disarm_system()
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        self._optimistic_state = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()
