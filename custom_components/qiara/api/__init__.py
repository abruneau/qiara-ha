"""API module for Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .client import QiaraApiClient
from ..models import QiaraSensorData

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
        room = ep_map["room"].strip()
        if room:
            # Name a placed node "<Room> <Type>" (e.g. "Sous Sol Door/Window")
            # so the room is readable and the sensor type stays visible. Nodes
            # without a room keep the default "Qiara <Type> <id>" name.
            label = _NODE_TYPE_LABELS.get(sensor.type, sensor.type.capitalize())
            short_label = label.removesuffix(" Sensor")
            updates["name"] = f"{room.title()} {short_label}"
    if "temperature" in ep_map and ep_map["temperature"] is not None:
        raw_temp = ep_map["temperature"]
        # The device reports temperature as {"timestamp": <unix>, "value": <int>}.
        # The value is whole degrees Celsius (e.g. 24 == 24 °C). A timestamp of 0
        # means the node has never reported a reading — its value is a sentinel
        # (200) rather than a real temperature, so leave it unset in that case.
        if (
            isinstance(raw_temp, dict)
            and raw_temp.get("value") is not None
            and raw_temp.get("timestamp")
        ):
            updates["temperature"] = float(raw_temp["value"])
    return sensor.model_copy(update=updates)


class QiaraApi:
    """Qiara API class for managing sensor data."""

    def __init__(self, session: ClientSession, customer_id: int, secret_key: str, base_url: str = "https://api.qiara.co/api/v1") -> None:
        """Initialize the Qiara API."""
        self._base_url = base_url.rstrip("/")
        self._client = QiaraApiClient(session, customer_id, secret_key, base_url)
        self._alarm_node_id: int | None = None
        self._camera_node_id: int | None = None
        self._camera_stream_name: str | None = None

    async def async_get_sensors(self) -> list[QiaraSensorData]:
        """Get all sensors with live state from Qiara API."""
        try:
            nodes_raw = await self._client.async_get_sensors()

            # Discover and cache alarm and camera node IDs
            for node in nodes_raw:
                if node.get("type_name") == "Node.HlAlarm":
                    self._alarm_node_id = int(node["id"])
                elif node.get("type_name") == "Node.HlCam":
                    self._camera_node_id = int(node["id"])

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

    async def async_arm_system(self, mode: str) -> bool:
        """Arm the Qiara system in the specified mode."""
        _LOGGER.debug("Qiara: async_arm_system called, mode=%s, alarm_node_id=%s", mode, self._alarm_node_id)
        if self._alarm_node_id is None:
            raise UpdateFailed("Alarm node not yet discovered — wait for first coordinator refresh")
        try:
            result = await self._client.async_arm_system(self._alarm_node_id, mode)
            _LOGGER.debug("Qiara: async_arm_system client call returned: %s", result)
            return result
        except Exception as ex:
            _LOGGER.error("Error arming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to arm system: {ex}")

    async def async_disarm_system(self) -> bool:
        """Disarm the Qiara system."""
        _LOGGER.debug("Qiara: async_disarm_system called, alarm_node_id=%s", self._alarm_node_id)
        if self._alarm_node_id is None:
            raise UpdateFailed("Alarm node not yet discovered — wait for first coordinator refresh")
        try:
            result = await self._client.async_disarm_system(self._alarm_node_id)
            _LOGGER.debug("Qiara: async_disarm_system client call returned: %s", result)
            return result
        except Exception as ex:
            _LOGGER.error("Error disarming Qiara system: %s", ex)
            raise UpdateFailed(f"Failed to disarm system: {ex}")

    def get_camera_node_id(self) -> int | None:
        """Return the camera node ID discovered from the nodes list."""
        return self._camera_node_id

    async def async_ensure_session(self) -> str:
        """Return a valid session ID, re-authenticating if needed."""
        return await self._client._ensure_session()

    async def async_activate_camera(self, camera_node_id: int) -> None:
        """Open the camera shutter (shutter=false means open/streaming)."""
        try:
            await self._client.async_write_endpoint(camera_node_id, "shutter", False)
        except Exception as ex:
            _LOGGER.error("Error activating Qiara camera: %s", ex)
            raise UpdateFailed(f"Failed to activate camera: {ex}")

    async def async_deactivate_camera(self, camera_node_id: int) -> None:
        """Close the camera shutter (shutter=true means closed/stopped)."""
        try:
            await self._client.async_write_endpoint(camera_node_id, "shutter", True)
        except Exception as ex:
            _LOGGER.error("Error deactivating Qiara camera: %s", ex)
            raise UpdateFailed(f"Failed to deactivate camera: {ex}")

    async def async_get_camera_snapshot(self, camera_node_id: int) -> bytes | None:
        """Return a JPEG snapshot only if the camera is already streaming.

        Deliberately does NOT open the shutter: a privacy-shutter security
        camera must not reveal a live frame just to render a dashboard
        thumbnail. live.jpeg only returns an image while the shutter is open
        (i.e. during an active stream); otherwise this returns None.
        """
        try:
            return await self._client.async_get_snapshot()
        except Exception as ex:
            _LOGGER.debug("Qiara: could not fetch camera snapshot: %s", ex)
            return None

    async def async_open_stream(self, force: bool = False) -> dict[str, Any]:
        """Open a stream session; returns SRT credentials (passphrase, pub_id)."""
        return await self._client.async_open_stream(force)

    def get_camera_stream_name(self) -> str | None:
        """Return the cached HLS stream name (e.g. 'HLS_TEST')."""
        return self._camera_stream_name

    async def async_fetch_camera_stream_name(self, camera_node_id: int) -> str | None:
        """Fetch and cache the HLS stream basename from the camera node.

        The 'stream' endpoint returns a full URL like:
          eup://02708940165a502a/api/v1/home/stream/HLS_TEST.m3u8
        We extract just the stem: 'HLS_TEST'.
        """
        if self._camera_stream_name:
            return self._camera_stream_name
        try:
            results = await self._client.async_read_endpoints(
                [{"node_id": camera_node_id, "eps": ["eup_id", "stream"]}]
            )
            for entry in results:
                ep_map = {ep["ep_name"]: ep["value"] for ep in entry.get("ep_values", [])}
                stream_url = ep_map.get("stream", "")
                if stream_url:
                    # Extract basename without extension from URL path
                    # e.g. "eup://…/home/stream/HLS_TEST.m3u8" → "HLS_TEST"
                    basename = stream_url.rstrip("/").split("/")[-1]
                    name = basename.split(".")[0] if "." in basename else basename
                    if name:
                        self._camera_stream_name = name
                        _LOGGER.debug("Qiara camera stream name: %s", name)
                        return name
        except Exception as ex:
            _LOGGER.warning("Could not read camera stream name: %s", ex)
        return None

    async def async_get_alarm_state(self) -> str | None:
        """Get the current alarm state from the Qiara API."""
        if self._alarm_node_id is None:
            _LOGGER.warning("Qiara: async_get_alarm_state — alarm_node_id is None")
            return None
        try:
            results = await self._client.async_read_endpoints(
                [{"node_id": self._alarm_node_id, "eps": ["hl_alarm_status"]}]
            )
            _LOGGER.debug("Qiara: async_get_alarm_state raw results: %s", results)
            for entry in results:
                for ep in entry.get("ep_values", []):
                    if ep["ep_name"] == "hl_alarm_status":
                        _LOGGER.debug("Qiara: async_get_alarm_state returning: %s", ep["value"])
                        return ep["value"]
            _LOGGER.warning("Qiara: async_get_alarm_state — hl_alarm_status not found in results")
            return None
        except Exception as ex:
            _LOGGER.warning("Qiara: async_get_alarm_state failed: %s", ex)
            return None