"""Camera platform for Qiara integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from urllib.parse import urlsplit

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

# Grace after opening the shutter before the camera produces video; without it
# HA's first SRT connect races the camera startup and errors ("Invalid data").
_SHUTTER_WARMUP_SECONDS = 3

# SRT low-latency live path. The hub runs an SRT listener on UDP 9000 reachable
# at the hub's own IP; streamid = stream name and passphrase = /home/open_stream
# both come from the local API. HA's own PyAV can't open SRT, so we register the
# stream with HA's bundled go2rtc (which restreams it via ffmpeg) and hand HA the
# resulting local RTSP URL — smooth, since it's local and SRT keeps up with the
# live edge (unlike the remote HLS path, which stutters as segments expire).
OPT_USE_SRT = "use_srt"
OPT_SRT_PORT = "srt_port"
OPT_SRT_LATENCY = "srt_latency"
DEFAULT_SRT_PORT = 9000

# HA's managed go2rtc: its config lives under hass.data["go2rtc"] (a UnixConnector
# session + placeholder URL) and it serves RTSP on this fixed local port.
GO2RTC_DATA_KEY = "go2rtc"
GO2RTC_RTSP_PORT = 18554


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
    host: str,
    port: int | str,
    streamid: str,
    passphrase: str,
    latency: int = 500000,
) -> str:
    """Build the caller-mode SRT URL for the hub's low-latency live stream.

    The hub runs an SRT listener (srt-daemon) on UDP 9000; the client connects
    as caller with the stream name as streamid and the passphrase returned by
    /home/open_stream. latency is in microseconds (500ms; a large buffer delays
    the first frame past PyAV's probe window and HA fails to open the stream).
    """
    params = (
        f"streamid={streamid}&passphrase={passphrase}"
        f"&mode=caller&transtype=live&latency={latency}"
    )
    return f"srt://{host}:{port}?{params}"


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
        self._shutter_task: asyncio.Task | None = None

        # SRT low-latency live path (see build_srt_url). Enabled by default and
        # falls back to HLS if it can't be built; options can disable it or
        # tune the port/latency.
        opts = entry.options
        self._use_srt: bool = bool(opts.get(OPT_USE_SRT, True))
        self._srt_port = opts.get(OPT_SRT_PORT, DEFAULT_SRT_PORT)
        # 500ms: the hub's SRT peerlatency floor. A large latency (e.g. 3s)
        # delays the first frame past PyAV's probe window and HA fails to open
        # the stream ("Invalid data found"); 500ms opens reliably on the LAN.
        self._srt_latency = int(opts.get(OPT_SRT_LATENCY, 500000))

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
        """Register the hub's SRT stream with go2rtc and return its RTSP URL.

        HA's PyAV can't open SRT directly, so go2rtc restreams it (via ffmpeg)
        and HA reads the resulting local RTSP. Everything comes from the local
        API: SRT listener on the hub's own host:9000, streamid = stream name,
        passphrase = /home/open_stream. Returns None (fall back to HLS) if any
        piece — go2rtc, streamid, or credentials — is unavailable.
        """
        go2rtc = self.hass.data.get(GO2RTC_DATA_KEY)
        session = getattr(go2rtc, "session", None)
        url = getattr(go2rtc, "url", None)
        if not (session and url):
            _LOGGER.debug("Qiara SRT: go2rtc unavailable — falling back to HLS")
            return None

        api = self.coordinator.api
        camera_node_id = api.get_camera_node_id()
        if camera_node_id is None:
            return None
        streamid = (
            api.get_camera_stream_name()
            or await api.async_fetch_camera_stream_name(camera_node_id)
        )
        host = urlsplit(api._base_url).hostname
        if not (streamid and host):
            _LOGGER.debug("Qiara SRT: missing streamid/host — falling back to HLS")
            return None

        creds = await api.async_open_stream(force=True)
        passphrase = creds.get("passphrase")
        if not passphrase:
            _LOGGER.debug("Qiara SRT: no passphrase from open_stream — falling back to HLS")
            return None

        # SRT only carries video while the camera is capturing, so open the
        # shutter now; the watcher below closes it again when viewing stops.
        # The camera needs a moment after the shutter opens before it produces
        # video, so wait briefly — otherwise HA's first connect races the
        # startup and fails with "Invalid data found" before retrying.
        with contextlib.suppress(Exception):
            await api.async_activate_camera(camera_node_id)
        await asyncio.sleep(_SHUTTER_WARMUP_SECONDS)

        srt_url = build_srt_url(host, self._srt_port, streamid, passphrase, self._srt_latency)
        # go2rtc pulls SRT via ffmpeg; copy the HEVC video (no transcode) and
        # remux audio to AAC (raw AAC-in-RTSP copy is rejected by the muxer).
        source = f"ffmpeg:{srt_url}#video=copy#audio=aac"
        name = f"qiara_camera_{camera_node_id}"
        try:
            from go2rtc_client import Go2RtcRestClient

            client = Go2RtcRestClient(session, url)
            await client.streams.add(name, source)
        except Exception as err:  # noqa: BLE001 - degrade to HLS on any failure
            _LOGGER.warning(
                "Qiara SRT: could not register go2rtc stream, falling back to HLS: %s", err
            )
            return None

        # Nothing in the SRT path closes the physical shutter once HA stops
        # viewing (unlike the HLS proxy's idle timer), so watch go2rtc for this
        # stream's consumers and close the shutter when they drop to zero.
        self._start_shutter_watcher(session, url, name, camera_node_id)

        _LOGGER.debug("Qiara SRT via go2rtc: rtsp://127.0.0.1:%s/%s", GO2RTC_RTSP_PORT, name)
        return f"rtsp://127.0.0.1:{GO2RTC_RTSP_PORT}/{name}"

    def _start_shutter_watcher(self, session, url: str, stream_name: str, camera_node_id: int) -> None:
        """Ensure a single background task is watching this stream's consumers."""
        if self._shutter_task and not self._shutter_task.done():
            return
        self._shutter_task = self.hass.async_create_background_task(
            self._watch_shutter(session, url, stream_name, camera_node_id),
            name=f"qiara_shutter_watch_{stream_name}",
        )

    async def _watch_shutter(self, session, url: str, stream_name: str, camera_node_id: int) -> None:
        """Close the camera shutter once go2rtc has no consumers for the stream.

        Polls go2rtc's raw /api/streams (the typed client drops the consumer
        list). Waits for a consumer to appear first (stream startup), then
        closes the shutter after it has been idle for a short grace period — or
        gives up and closes it if the stream never started.
        """
        poll, grace, startup = 10, 2, 6
        idle = polls = 0
        seen = False
        streams_url = url.rstrip("/") + "/api/streams"
        try:
            while True:
                await asyncio.sleep(poll)
                polls += 1
                try:
                    async with session.get(streams_url) as resp:
                        info = (await resp.json()).get(stream_name) or {}
                    consumers = len(info.get("consumers") or [])
                except Exception:  # noqa: BLE001 - treat query failure as idle
                    consumers = 0
                if consumers > 0:
                    seen, idle = True, 0
                elif seen:
                    idle += 1
                    if idle >= grace:
                        break
                elif polls >= startup:
                    break  # stream never started; close the shutter anyway
        finally:
            with contextlib.suppress(Exception):
                await self.coordinator.api.async_deactivate_camera(camera_node_id)
            _LOGGER.debug("Qiara: closed camera %s shutter (stream ended)", camera_node_id)

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

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the shutter watcher and close the shutter on unload."""
        if self._shutter_task and not self._shutter_task.done():
            self._shutter_task.cancel()
        await super().async_will_remove_from_hass()
