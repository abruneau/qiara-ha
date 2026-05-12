"""Data update coordinator for Qiara."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import QiaraApi
from .models import QiaraSensorData

_LOGGER = logging.getLogger(__name__)


class QiaraDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Qiara data updates."""

    def __init__(
        self,
        hass,
        api: QiaraApi,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name="Qiara",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Qiara API."""
        try:
            sensors = await self.api.async_get_sensors()
            result: dict[str, Any] = {sensor.id: sensor for sensor in sensors}
            result["alarm_state"] = await self.api.async_get_alarm_state()
            return result
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Error fetching data from Qiara API: %s", ex)
            raise UpdateFailed(f"Error updating data: {ex}")

    async def async_push_event(self, event: dict) -> None:
        """Handle a real-time push event from qiara-ha-bridge."""
        value = event.get("value", "")
        node_id = event.get("node_id")

        _ALARM_VALUE_MAP = {
            "alarm_triggered": "triggered",
            "alarm_disabled": "off",
            "alarm_enabled_full": "day_armed",
            "alarm_enabled_partial": "night_armed",
        }

        if value in _ALARM_VALUE_MAP:
            if self.data is not None:
                self.data["alarm_state"] = _ALARM_VALUE_MAP[value]
                self.async_update_listeners()
            return

        sensor_key = str(node_id)
        if self.data is None or sensor_key not in self.data:
            _LOGGER.debug("push_event: unknown node_id %s, ignoring", node_id)
            return

        sensor_data = self.data[sensor_key]
        if not isinstance(sensor_data, QiaraSensorData):
            return

        if value in ("dws_open", "mvt_detected"):
            new_state: str | None = value
        elif value in ("dws_close", "mvt_cleared"):
            new_state = None
        else:
            _LOGGER.debug("push_event: unhandled value %r for node %s", value, node_id)
            return

        self.data[sensor_key] = sensor_data.model_copy(
            update={"state": new_state, "last_updated": datetime.now()}
        )
        self.async_update_listeners()