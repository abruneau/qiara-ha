"""API module for Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, UpdateFailed

from .client import QiaraApiClient
from ..models import QiaraSensorList, QiaraSensorData

_LOGGER = logging.getLogger(__name__)

class QiaraApi:
    """Qiara API class for managing sensor data."""

    def __init__(self, session: ClientSession, api_key: str, base_url: str = "https://api.qiara.com") -> None:
        """Initialize the Qiara API."""
        self._client = QiaraApiClient(session, api_key, base_url)

    async def async_get_sensors(self) -> list[QiaraSensorData]:
        """Get all sensors from Qiara API with Pydantic validation."""
        try:
            sensors_raw = await self._client.async_get_sensors()
            return QiaraSensorList(sensors=sensors_raw).sensors
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Error fetching or validating sensors from Qiara API: %s", ex)
            raise UpdateFailed(f"Failed to fetch sensors: {ex}")

    async def async_get_sensor_data(self, sensor_id: str) -> QiaraSensorData:
        """Get specific sensor data from Qiara API with Pydantic validation."""
        try:
            sensor_raw = await self._client.async_get_sensor_data(sensor_id)
            return QiaraSensorData.model_validate(sensor_raw)
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Error fetching sensor data from Qiara API: %s", ex)
            raise UpdateFailed(f"Failed to fetch sensor data: {ex}")

    async def async_arm_system(self, mode: str) -> bool:
        """Arm the Qiara system in the specified mode."""
        try:
            result = await self._client.async_arm_system(mode)
            return result
        except Exception as ex:
            _LOGGER.error("Error arming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to arm system: {ex}")

    async def async_disarm_system(self) -> bool:
        """Disarm the Qiara system."""
        try:
            result = await self._client.async_disarm_system()
            return result
        except Exception as ex:
            _LOGGER.error("Error disarming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to disarm system: {ex}")