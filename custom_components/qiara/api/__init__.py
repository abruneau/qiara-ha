"""API module for Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .client import QiaraApiClient
from ..models import QiaraSensorList, QiaraSensorData

_LOGGER = logging.getLogger(__name__)


_NODE_TYPE_MAP = {
    "Node.HlCam": "camera",
    "Node.HlAlarm": "alarm",
    "Node.DomusNode.HlSrn": "siren",
    "Node.DomusNode.HlDws": "door",
    "Node.DomusNode.HlPir": "motion",
    "Node.DomusNode.HLKpd": "keypad",
}

_NODE_TYPE_LABELS = {
    "door": "Door/Window Sensor",
    "motion": "Motion Sensor",
    "siren": "Siren",
    "camera": "Camera",
    "keypad": "Keypad",
}

_SENSOR_ENDPOINTS = ["state", "battery", "reachable", "room", "temperature"]


def _map_node(node: dict[str, Any]) -> dict[str, Any]:
    """Map SDK Node dict fields to QiaraSensorData-compatible fields."""
    node_id = str(node.get("id", ""))
    raw_type = node.get("type_name", "unknown")
    mapped_type = _NODE_TYPE_MAP.get(raw_type, raw_type.lower())
    label = _NODE_TYPE_LABELS.get(mapped_type, mapped_type.capitalize())
    return {
        "id": node_id,
        "name": f"Qiara {label} {node_id}",
        "type": mapped_type,
        "available": not bool(node.get("discarded", 0)),
    }


def _apply_endpoints(sensor: QiaraSensorData, ep_values: list[dict]) -> QiaraSensorData:
    """Enrich a QiaraSensorData with live endpoint values."""
    ep_map = {ep["ep_name"]: ep["value"] for ep in ep_values}
    updates: dict[str, Any] = {}
    if "state" in ep_map:
        updates["state"] = ep_map["state"]
    if "battery" in ep_map and ep_map["battery"] is not None:
        updates["battery_level"] = int(ep_map["battery"])
    if "reachable" in ep_map:
        updates["available"] = bool(ep_map["reachable"])
    if "room" in ep_map and ep_map["room"]:
        updates["name"] = ep_map["room"].strip()
    if "temperature" in ep_map and ep_map["temperature"] is not None:
        raw_temp = ep_map["temperature"]
        if isinstance(raw_temp, dict) and raw_temp.get("value") is not None:
            updates["temperature"] = raw_temp["value"] / 10.0
    return sensor.model_copy(update=updates)


class QiaraApi:
    """Qiara API class for managing sensor data."""

    def __init__(self, session: ClientSession, customer_id: int, secret_key: str, base_url: str = "https://api.qiara.co/api/v1") -> None:
        """Initialize the Qiara API."""
        self._client = QiaraApiClient(session, customer_id, secret_key, base_url)
        self._alarm_node_id: int | None = None

    async def async_get_sensors(self) -> list[QiaraSensorData]:
        """Get all sensors with live state from Qiara API."""
        try:
            nodes_raw = await self._client.async_get_sensors()

            # Discover and cache the alarm node ID
            for node in nodes_raw:
                if node.get("type_name") == "Node.HlAlarm":
                    self._alarm_node_id = int(node["id"])

            # Read live endpoint values for DomusNodes (have adapter_id)
            domus_nodes = [n for n in nodes_raw if n.get("adapter_id") is not None]
            ep_by_node: dict[str, list] = {}
            if domus_nodes:
                items = [{"node_id": int(n["id"]), "eps": _SENSOR_ENDPOINTS} for n in domus_nodes]
                ep_results = await self._client.async_read_endpoints(items)
                ep_by_node = {str(r["node_id"]): r.get("ep_values", []) for r in ep_results}

            sensors = []
            for node in nodes_raw:
                sensor = QiaraSensorData(**_map_node(node))
                node_id = str(node["id"])
                if node_id in ep_by_node:
                    sensor = _apply_endpoints(sensor, ep_by_node[node_id])
                sensors.append(sensor)
            return sensors
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Error fetching sensors from Qiara API: %s", ex)
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
        if self._alarm_node_id is None:
            raise UpdateFailed("Alarm node not yet discovered — wait for first coordinator refresh")
        try:
            return await self._client.async_arm_system(self._alarm_node_id, mode)
        except Exception as ex:
            _LOGGER.error("Error arming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to arm system: {ex}")

    async def async_disarm_system(self) -> bool:
        """Disarm the Qiara system."""
        if self._alarm_node_id is None:
            raise UpdateFailed("Alarm node not yet discovered — wait for first coordinator refresh")
        try:
            return await self._client.async_disarm_system(self._alarm_node_id)
        except Exception as ex:
            _LOGGER.error("Error disarming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to disarm system: {ex}")