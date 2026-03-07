"""Data update coordinator for Qiara."""
from __future__ import annotations

import logging
from datetime import timedelta
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
            update_interval=timedelta(seconds=15),
        )

    async def _async_update_data(self) -> dict[str, QiaraSensorData]:
        """Fetch data from the Qiara API."""
        try:
            sensors = await self.api.async_get_sensors()
            return {sensor.id: sensor for sensor in sensors}
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Error fetching data from Qiara API: %s", ex)
            raise UpdateFailed(f"Error updating data: {ex}")