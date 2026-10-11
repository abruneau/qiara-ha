"""Data update coordinator for Qiara."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import QiaraApi

_LOGGER = logging.getLogger(__name__)


class QiaraDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage Qiara data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: QiaraApi,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        # Device registry id of the hub device; set in async_setup_entry.
        self.hub_device_id: str | None = None

        # Pass the entry explicitly rather than letting the base class fall back
        # to the `current_entry` ContextVar: that var is only populated inside
        # HA's config entry setup context, so any setup path outside it would
        # leave `config_entry` as None and break async_config_entry_first_refresh.
        super().__init__(
            hass,
            _LOGGER,
            name="Qiara",
            update_interval=timedelta(seconds=60),
            config_entry=entry,
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
