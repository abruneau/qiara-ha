"""API module for Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, UpdateFailed

from .client import QiaraApiClient
from ..models import QiaraSensorList, QiaraSensorData

_LOGGER = logging.getLogger(__name__)


def _map_node(node: dict[str, Any]) -> dict[str, Any]:
    """Map SDK Node dict fields to QiaraSensorData-compatible fields."""
    node_id = str(node.get("id", ""))
    type_name = node.get("type_name", "unknown")
    return {
        "id": node_id,
        "name": f"Qiara {type_name.capitalize()} {node_id}",
        "type": type_name,
        "state": "unknown",
        "available": not bool(node.get("discarded", 0)),
    }


class QiaraApi:
    """Qiara API class for managing sensor data."""

    def __init__(self, session: ClientSession, customer_id: int, secret_key: str, base_url: str = "https://api.qiara.co/api/v1") -> None:
        """Initialize the Qiara API."""
        self._client = QiaraApiClient(session, customer_id, secret_key, base_url)

    async def async_get_sensors(self) -> list[QiaraSensorData]:
        """Get all sensors from Qiara API with Pydantic validation."""
        try:
            sensors_raw = await self._client.async_get_sensors()
            mapped = [_map_node(n) for n in sensors_raw]
            return QiaraSensorList(sensors=mapped).sensors
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