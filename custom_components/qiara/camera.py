"""Camera platform for Qiara integration."""

from __future__ import annotations

import asyncio
import logging
import time

from aiohttp import web
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .models import QiaraSensorData

_LOGGER = logging.getLogger(__name__)

# hass.data[DOMAIN] key holding the singleton stream-proxy view.
_CAMERA_PROXY_KEY = "_camera_stream_proxy"

# Snapshot cache TTL — avoids re-opening the shutter on every thumbnail poll.
_SNAPSHOT_CACHE_SECONDS = 10

# Options keys for the (opt-in, experimental) SRT low-latency live path.
OPT_USE_SRT = "use_srt"
OPT_SRT_HOST = "srt_host"
OPT_SRT_PORT = "srt_port"
OPT_SRT_LATENCY = "srt_latency"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qiara camera entities from config entry."""
    coordinator: QiaraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register the stream proxy view once (it resolves the active coordinator at
    # request time, so it survives reloads and is shared across entries). Cancel
    # its idle timers when this entry unloads.
    proxy: QiaraCameraStreamProxy | None = hass.data[DOMAIN].get(_CAMERA_PROXY_KEY)
    if proxy is None:
        proxy = QiaraCameraStreamProxy()
        hass.http.register_view(proxy)
        hass.data[DOMAIN][_CAMERA_PROXY_KEY] = proxy
    entry.async_on_unload(proxy.shutdown)

    # Older versions registered the camera with has_entity_name=True plus a name
    # equal to the device name, producing a doubled friendly name ("Qiara
    # Camera 1 Qiara Camera 1"). That flag is sticky in the registry, so drop
    # the stale entry and let it re-register cleanly. New entries register with
    # has_entity_name=False and won't match this.
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.domain == "camera" and reg_entry.has_entity_name:
            ent_reg.async_remove(reg_entry.entity_id)

    cameras = [
        QiaraCamera(coordinator, entry, sensor_id)
        for sensor_id, data in coordinator.data.items()
        if isinstance(data, QiaraSensorData) and data.type == "camera"
    ]
    async_add_entities(cameras)


def build_srt_url(
    host: str, port: int | str, streamid: str, passphrase: str, latency: int | None = None
) -> str:
    """Build the SRT stream URL the Qiara app uses for low-latency live video."""
    params = [f"streamid={streamid}", f"passphrase={passphrase}"]
    if latency:
        params.append(f"latency={latency}")
    return f"srt://{host}:{port}?{'&'.join(params)}"


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
    _CHUNK = 64 * 1024

    def __init__(self) -> None:
        self._shutter_open: set[int] = set()
        self._idle_tasks: dict[int, asyncio.Task] = {}

    @staticmethod
    def _get_api(hass: HomeAssistant):
        """Return the API of the first active Qiara coordinator, or None."""
        for value in hass.data.get(DOMAIN, {}).values():
            if isinstance(value, QiaraDataUpdateCoordinator):
                return value.api
        return None

    async def get(
        self,
        request: web.Request,
        node_id: str,
        file: str,
        quality: str | None = None,
    ) -> web.StreamResponse:
        """Proxy a stream request to the device, activating the shutter on first access."""
        hass = request.app["hass"]
        api = self._get_api(hass)
        if api is None:
            return web.Response(status=503, text="Qiara integration not loaded")

        session = async_get_clientsession(hass, verify_ssl=False)
        node_id_int = int(node_id)

        # Activate shutter once per camera (idempotent on the device)
        if node_id_int not in self._shutter_open:
            try:
                await api.async_activate_camera(node_id_int)
                self._shutter_open.add(node_id_int)
                _LOGGER.debug("Qiara: camera %s shutter opened via proxy", node_id)
            except Exception as err:
                _LOGGER.warning("Qiara: could not activate camera shutter: %s", err)

        # Reset the idle timer — shutter closes if no segment arrives within _IDLE_TIMEOUT
        self._reset_idle_timer(hass, api, node_id_int)

        tail = f"{quality}/{file}" if quality else file
        upstream_url = f"{api._base_url}/home/stream/{tail}"

        try:
            session_id = await api.async_ensure_session()
            async with session.get(
                upstream_url,
                headers={"x-hlcore-session-id": session_id},
                ssl=False,
            ) as resp:
                # Stream the upstream body through in chunks rather than buffering
                # the whole segment in memory — lower memory use and latency.
                downstream = web.StreamResponse(
                    status=resp.status,
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                downstream.content_type = resp.content_type or "application/octet-stream"
                await downstream.prepare(request)
                async for chunk in resp.content.iter_chunked(self._CHUNK):
                    await downstream.write(chunk)
                await downstream.write_eof()
                return downstream
        except Exception as err:
            _LOGGER.warning("Qiara stream proxy error for %s: %s", tail, err)
            return web.Response(status=502, text=str(err))

    def _reset_idle_timer(self, hass: HomeAssistant, api, node_id: int) -> None:
        """Cancel any existing idle timer and start a fresh one."""
        existing = self._idle_tasks.pop(node_id, None)
        if existing:
            existing.cancel()
        # Background task so HA cancels it automatically at shutdown instead of
        # warning that a non-critical task is still running.
        self._idle_tasks[node_id] = hass.async_create_background_task(
            self._close_after_idle(api, node_id),
            name=f"qiara_camera_{node_id}_idle_close",
        )

    async def _close_after_idle(self, api, node_id: int) -> None:
        """Close the shutter after the idle timeout expires."""
        try:
            await asyncio.sleep(self._IDLE_TIMEOUT)
        except asyncio.CancelledError:
            return
        _LOGGER.debug("Qiara: camera %s stream idle — closing shutter", node_id)
        try:
            await api.async_deactivate_camera(node_id)
        except Exception as err:
            _LOGGER.warning("Qiara: failed to close shutter after idle: %s", err)
        finally:
            self._shutter_open.discard(node_id)
            self._idle_tasks.pop(node_id, None)

    def shutdown(self) -> None:
        """Cancel outstanding idle timers (called when an entry unloads)."""
        for task in self._idle_tasks.values():
            task.cancel()
        self._idle_tasks.clear()
        self._shutter_open.clear()


class QiaraCamera(CoordinatorEntity, Camera):
    """Qiara camera entity providing HLS streaming via a local auth proxy."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: QiaraDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
    ) -> None:
        """Initialize the camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._sensor_id = sensor_id
        self._attr_unique_id = f"qiara_camera_{sensor_id}"
        self._last_image: bytes | None = None
        self._last_image_ts: float = 0.0

        # Experimental opt-in SRT low-latency path (see build_srt_url). The SRT
        # host/port live in the camera's provisioning data, which the local
        # polling API does not expose, so they must be supplied via options.
        opts = entry.options
        self._use_srt: bool = bool(opts.get(OPT_USE_SRT, False))
        self._srt_host: str | None = opts.get(OPT_SRT_HOST)
        self._srt_port = opts.get(OPT_SRT_PORT)
        self._srt_latency = opts.get(OPT_SRT_LATENCY)

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
        """Return the live stream URL — SRT if enabled/available, else HLS."""
        if self._use_srt:
            srt_url = await self._async_srt_stream_source()
            if srt_url:
                return srt_url
        return await self._async_hls_stream_source()

    async def _async_hls_stream_source(self) -> str | None:
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

    async def _async_srt_stream_source(self) -> str | None:
        """Return an SRT stream URL for low-latency live video (experimental).

        Falls back (returns None) when the pieces SRT needs aren't available:
        the stream id (from the camera node) and the SRT host/port. The latter
        come from camera provisioning and are not exposed by the local polling
        API, so they must be configured via the integration options.
        """
        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is None:
            return None

        streamid = (
            api.get_camera_stream_name()
            or await api.async_fetch_camera_stream_name(camera_node_id)
        )
        if not (streamid and self._srt_host and self._srt_port):
            _LOGGER.debug(
                "Qiara SRT: missing streamid/host/port — falling back to HLS "
                "(set %s/%s/%s in the integration options to enable SRT)",
                OPT_USE_SRT, OPT_SRT_HOST, OPT_SRT_PORT,
            )
            return None

        creds = await api.async_open_stream(force=False)
        passphrase = creds.get("passphrase")
        if not passphrase:
            _LOGGER.debug("Qiara SRT: no passphrase from open_stream — falling back to HLS")
            return None

        _LOGGER.debug(
            "Qiara SRT stream: srt://%s:%s?streamid=%s&passphrase=***",
            self._srt_host, self._srt_port, streamid,
        )
        return build_srt_url(
            self._srt_host, self._srt_port, streamid, passphrase, self._srt_latency
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera's live.jpeg snapshot endpoint.

        Cached briefly so repeated thumbnail polls don't re-open the shutter.
        """
        now = time.monotonic()
        if self._last_image and now - self._last_image_ts < _SNAPSHOT_CACHE_SECONDS:
            return self._last_image

        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is None:
            return self._last_image

        image = await api.async_get_camera_snapshot(camera_node_id)
        if image:
            self._last_image = image
            self._last_image_ts = now
        return self._last_image

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
