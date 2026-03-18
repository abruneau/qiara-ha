"""Camera platform for Qiara integration."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .models import QiaraSensorData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qiara camera entities from config entry."""
    coordinator: QiaraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register the stream proxy view so ffmpeg can reach the device through HA
    # (avoids ffmpeg having to verify the device's self-signed TLS certificate)
    hass.http.register_view(
        QiaraCameraStreamProxy(coordinator.api, coordinator.api._base_url)
    )

    cameras = [
        QiaraCamera(coordinator, sensor_id)
        for sensor_id, data in coordinator.data.items()
        if isinstance(data, QiaraSensorData) and data.type == "camera"
    ]
    async_add_entities(cameras)


class QiaraCameraStreamProxy(HomeAssistantView):
    """Proxy Qiara HLS stream requests, injecting the session auth header.

    Two URL patterns cover the full HLS tree:
      /api/qiara/camera/{node_id}/stream/{file}          ← master playlist
      /api/qiara/camera/{node_id}/stream/{quality}/{file} ← quality playlist + segments
    """

    url = "/api/qiara/camera/{node_id}/stream/{file}"
    extra_urls = ["/api/qiara/camera/{node_id}/stream/{quality}/{file}"]
    name = "api:qiara:camera:stream"
    requires_auth = False
    cors_allowed = True

    _IDLE_TIMEOUT = 20  # seconds after last segment request before closing the shutter

    def __init__(self, api, device_base_url: str) -> None:
        self._api = api
        self._device_base_url = device_base_url
        self._shutter_open: set[int] = set()
        self._idle_tasks: dict[int, asyncio.Task] = {}

    async def get(
        self,
        request: web.Request,
        node_id: str,
        file: str,
        quality: str | None = None,
    ) -> web.Response:
        """Proxy a stream request to the device, activating the shutter on first access."""
        hass = request.app["hass"]
        session = async_get_clientsession(hass, verify_ssl=False)
        node_id_int = int(node_id)

        # Activate shutter once per camera (idempotent on the device)
        if node_id_int not in self._shutter_open:
            try:
                await self._api.async_activate_camera(node_id_int)
                self._shutter_open.add(node_id_int)
                _LOGGER.debug("Qiara: camera %s shutter opened via proxy", node_id)
            except Exception as err:
                _LOGGER.warning("Qiara: could not activate camera shutter: %s", err)

        # Reset the idle timer — shutter closes if no segment arrives within _IDLE_TIMEOUT
        self._reset_idle_timer(hass, node_id_int)

        tail = f"{quality}/{file}" if quality else file
        upstream_url = f"{self._device_base_url}/home/stream/{tail}"

        try:
            session_id = await self._api.async_ensure_session()
            async with session.get(
                upstream_url,
                headers={"x-hlcore-session-id": session_id},
                ssl=False,
            ) as resp:
                body = await resp.read()
                return web.Response(
                    body=body,
                    status=resp.status,
                    content_type=resp.content_type or "application/octet-stream",
                    headers={"Access-Control-Allow-Origin": "*"},
                )
        except Exception as err:
            _LOGGER.warning("Qiara stream proxy error for %s: %s", tail, err)
            return web.Response(status=502, text=str(err))

    def _reset_idle_timer(self, hass: HomeAssistant, node_id: int) -> None:
        """Cancel any existing idle timer and start a fresh one."""
        existing = self._idle_tasks.pop(node_id, None)
        if existing:
            existing.cancel()
        self._idle_tasks[node_id] = hass.async_create_task(
            self._close_after_idle(node_id)
        )

    async def _close_after_idle(self, node_id: int) -> None:
        """Close the shutter after the idle timeout expires."""
        await asyncio.sleep(self._IDLE_TIMEOUT)
        _LOGGER.debug("Qiara: camera %s stream idle — closing shutter", node_id)
        try:
            await self._api.async_deactivate_camera(node_id)
        except Exception as err:
            _LOGGER.warning("Qiara: failed to close shutter after idle: %s", err)
        finally:
            self._shutter_open.discard(node_id)
            self._idle_tasks.pop(node_id, None)


class QiaraCamera(CoordinatorEntity, Camera):
    """Qiara camera entity providing HLS streaming via a local auth proxy."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        sensor_id: str,
    ) -> None:
        """Initialize the camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._sensor_id = sensor_id
        self._attr_unique_id = f"qiara_camera_{sensor_id}"

    @property
    def _sensor(self) -> QiaraSensorData | None:
        data = self.coordinator.data.get(self._sensor_id)
        return data if isinstance(data, QiaraSensorData) else None

    @property
    def name(self) -> str:
        sensor = self._sensor
        return sensor.name if sensor else f"Camera {self._sensor_id}"

    @property
    def available(self) -> bool:
        sensor = self._sensor
        return sensor is not None and sensor.available

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._sensor_id)},
            "name": self.name,
            "manufacturer": "Qiara",
        }

    async def stream_source(self) -> str | None:
        """Return the local proxy URL for the HLS stream."""
        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is None:
            return None

        stream_name = (
            api.get_camera_stream_name()
            or await api.async_fetch_camera_stream_name(camera_node_id)
        )
        if not stream_name:
            _LOGGER.warning("Qiara camera: could not retrieve stream name")
            return None

        ha_url = get_url(self.hass, allow_internal=True)
        return f"{ha_url}/api/qiara/camera/{camera_node_id}/stream/{stream_name}.m3u8"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return None — the stream component extracts keyframe snapshots."""
        return None

    async def async_turn_on(self) -> None:
        """Open the camera shutter."""
        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is not None:
            await api.async_activate_camera(camera_node_id)

    async def async_turn_off(self) -> None:
        """Close the camera shutter."""
        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is not None:
            await api.async_deactivate_camera(camera_node_id)
