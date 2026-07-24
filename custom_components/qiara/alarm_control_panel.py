"""Support for Qiara alarm control panel."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

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

from .const import DOMAIN, SYSTEM_MODE_DAY, SYSTEM_MODE_DISARMED, SYSTEM_MODE_NIGHT
from .coordinator import QiaraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_ALARM_STATE_MAP: dict[str, AlarmControlPanelState] = {
    SYSTEM_MODE_DAY: AlarmControlPanelState.ARMED_HOME,
    "day_armed": AlarmControlPanelState.ARMED_HOME,
    SYSTEM_MODE_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    "night_armed": AlarmControlPanelState.ARMED_NIGHT,
    SYSTEM_MODE_DISARMED: AlarmControlPanelState.DISARMED,
    "triggered": AlarmControlPanelState.TRIGGERED,
}

# Raw hl_alarm_status values that confirm each command has actually taken
# effect on the device (the endpoint returns both the "day"/"night"/"off"
# write values and the "day_armed"/"night_armed" poll values, see CLAUDE.md).
_ARM_CONFIRM_RAW: dict[str, tuple[str, ...]] = {
    SYSTEM_MODE_DAY: (SYSTEM_MODE_DAY, "day_armed"),
    SYSTEM_MODE_NIGHT: (SYSTEM_MODE_NIGHT, "night_armed"),
}
_DISARM_CONFIRM_RAW: tuple[str, ...] = (SYSTEM_MODE_DISARMED,)

# Confirmation is polled directly (single-endpoint read) instead of waiting
# for the coordinator's regular poll interval, so the widget can catch up
# quickly after a command instead of after the next full sync.
_CONFIRM_POLL_INTERVAL = 2  # seconds between confirmation polls
_CONFIRM_POLL_ATTEMPTS = 8  # ~14s worst case before giving up


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
        self._optimistic_state: AlarmControlPanelState | None = None

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the current alarm state.

        A freshly-set optimistic value (pending or just-confirmed-by-command)
        always wins over coordinator data, since coordinator data can be up
        to one poll interval stale right after a command. It's cleared once
        `_async_confirm_state` verifies the device agrees, so subsequent
        reads go back to tracking the coordinator (e.g. externally-triggered
        alarms).
        """
        if self._optimistic_state is not None:
            return self._optimistic_state
        raw = self.coordinator.data.get("alarm_state") if self.coordinator.data else None
        if raw is not None:
            return _ALARM_STATE_MAP.get(raw, AlarmControlPanelState.DISARMED)
        return AlarmControlPanelState.DISARMED

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm in home (day) mode."""
        await self._async_execute_command(
            lambda: self.coordinator.api.async_arm_system(SYSTEM_MODE_DAY),
            pending_state=AlarmControlPanelState.ARMING,
            final_state=AlarmControlPanelState.ARMED_HOME,
            confirm_raw=_ARM_CONFIRM_RAW[SYSTEM_MODE_DAY],
            error_context="async_alarm_arm_home",
        )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm in night mode."""
        await self._async_execute_command(
            lambda: self.coordinator.api.async_arm_system(SYSTEM_MODE_NIGHT),
            pending_state=AlarmControlPanelState.ARMING,
            final_state=AlarmControlPanelState.ARMED_NIGHT,
            confirm_raw=_ARM_CONFIRM_RAW[SYSTEM_MODE_NIGHT],
            error_context="async_alarm_arm_night",
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm system."""
        await self._async_execute_command(
            self.coordinator.api.async_disarm_system,
            pending_state=AlarmControlPanelState.DISARMING,
            final_state=AlarmControlPanelState.DISARMED,
            confirm_raw=_DISARM_CONFIRM_RAW,
            error_context="async_alarm_disarm",
        )

    async def _async_execute_command(
        self,
        api_call: Callable[[], Awaitable[object]],
        pending_state: AlarmControlPanelState,
        final_state: AlarmControlPanelState,
        confirm_raw: tuple[str, ...],
        error_context: str,
    ) -> None:
        """Run an arm/disarm command, showing pending/final state right away and confirming it against the device."""
        _LOGGER.debug("Qiara: %s called", error_context)
        self._optimistic_state = pending_state
        self.async_write_ha_state()

        try:
            await api_call()
        except Exception as err:
            _LOGGER.error("Qiara: %s failed: %s", error_context, err)
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(str(err)) from err

        _LOGGER.debug("Qiara: %s succeeded, setting optimistic state", error_context)
        self._optimistic_state = final_state
        self.async_write_ha_state()

        hass = getattr(self, "hass", None)
        if hass is not None:
            hass.async_create_task(self._async_confirm_state(confirm_raw))
        else:
            await self._async_confirm_state(confirm_raw)

    async def _async_confirm_state(self, confirm_raw: tuple[str, ...]) -> None:
        """Poll the device directly for hl_alarm_status until it matches the command, instead of waiting for the next scheduled sync."""
        for attempt in range(_CONFIRM_POLL_ATTEMPTS):
            if attempt > 0:
                await asyncio.sleep(_CONFIRM_POLL_INTERVAL)
            try:
                raw = await self.coordinator.api.async_get_alarm_state()
            except Exception as err:
                _LOGGER.debug("Qiara: confirm poll attempt %s failed: %s", attempt + 1, err)
                continue
            if raw in confirm_raw:
                if self.coordinator.data is not None:
                    self.coordinator.data["alarm_state"] = raw
                    self.coordinator.async_update_listeners()
                self._optimistic_state = None
                self.async_write_ha_state()
                return
        _LOGGER.warning(
            "Qiara: alarm state not confirmed within %ss, keeping optimistic state until next sync",
            _CONFIRM_POLL_INTERVAL * (_CONFIRM_POLL_ATTEMPTS - 1),
        )
