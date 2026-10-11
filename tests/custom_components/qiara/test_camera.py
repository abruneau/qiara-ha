"""Tests for Qiara camera helpers."""
from __future__ import annotations

from custom_components.qiara.camera import build_srt_url


def test_build_srt_url_basic():
    """SRT URL carries streamid, passphrase, and caller-mode live params."""
    url = build_srt_url("192.0.2.10", 9000, "HLS_TEST", "secret")
    assert url == (
        "srt://192.0.2.10:9000?streamid=HLS_TEST&passphrase=secret"
        "&mode=caller&transtype=live&latency=500000"
    )


def test_build_srt_url_custom_latency():
    """Latency override is reflected in the URL."""
    url = build_srt_url("192.0.2.10", "9000", "cam1", "pw", latency=1000000)
    assert url.endswith("&mode=caller&transtype=live&latency=1000000")
    assert url.startswith("srt://192.0.2.10:9000?streamid=cam1&passphrase=pw")


# --- Shutter lifecycle -------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.camera import Camera

from custom_components.qiara.camera import (
    _CAMERA_PROXY_KEY,
    GO2RTC_DATA_KEY,
    QiaraCamera,
    QiaraCameraStreamProxy,
)
from custom_components.qiara.const import DOMAIN
from custom_components.qiara.coordinator import QiaraDataUpdateCoordinator

CAMERA_NODE = 5


@pytest.fixture
def mock_api():
    """Mock QiaraApi with a discovered camera."""
    api = MagicMock()
    api._base_url = "https://192.0.2.10:64218/api/v1"
    api.get_camera_node_id.return_value = CAMERA_NODE
    api.get_camera_stream_name.return_value = "HLS_TEST"
    api.async_fetch_camera_stream_name = AsyncMock(return_value="HLS_TEST")
    api.async_open_stream = AsyncMock(return_value={"passphrase": "pw"})
    api.async_activate_camera = AsyncMock()
    api.async_deactivate_camera = AsyncMock()
    return api


@pytest.fixture
def camera(mock_api):
    """QiaraCamera wired to a fake hass with go2rtc and the HLS proxy."""
    coordinator = MagicMock()
    coordinator.api = mock_api
    entry = MagicMock()
    entry.options = {}
    cam = QiaraCamera(coordinator, entry, str(CAMERA_NODE))
    hass = MagicMock()
    hass.data = {
        GO2RTC_DATA_KEY: MagicMock(session=MagicMock(), url="http://localhost:11984/"),
        DOMAIN: {_CAMERA_PROXY_KEY: QiaraCameraStreamProxy()},
    }
    hass.async_create_background_task = MagicMock(
        side_effect=lambda coro, name: coro.close() or MagicMock(done=lambda: False)
    )
    cam.hass = hass
    return cam


@pytest.mark.asyncio
async def test_provider_probe_does_not_touch_shutter(camera, mock_api):
    """HA's provider probe (every start/reload) must not open the shutter."""
    seen = []

    async def fake_refresh(self, *, write_state=True):
        seen.append(await self.stream_source())

    with patch.object(Camera, "async_refresh_providers", fake_refresh):
        await camera.async_refresh_providers(write_state=False)

    assert seen == [f"rtsp://127.0.0.1:18554/qiara_camera_{CAMERA_NODE}"]
    mock_api.async_activate_camera.assert_not_called()
    mock_api.async_open_stream.assert_not_called()
    camera.hass.async_create_background_task.assert_not_called()


@pytest.mark.asyncio
async def test_real_stream_request_opens_shutter_and_starts_watcher(camera, mock_api):
    """A real viewer request opens the shutter, registers go2rtc, and watches it."""
    client = MagicMock()
    client.streams.add = AsyncMock()
    with patch("custom_components.qiara.camera.asyncio.sleep", AsyncMock()), patch(
        "go2rtc_client.Go2RtcRestClient", return_value=client
    ):
        url = await camera.stream_source()

    assert url == f"rtsp://127.0.0.1:18554/qiara_camera_{CAMERA_NODE}"
    mock_api.async_open_stream.assert_awaited_once_with(force=True)
    mock_api.async_activate_camera.assert_awaited_once_with(CAMERA_NODE)
    client.streams.add.assert_awaited_once()
    camera.hass.async_create_background_task.assert_called_once()


@pytest.mark.asyncio
async def test_go2rtc_failure_closes_shutter(camera, mock_api):
    """If go2rtc registration fails nothing watches the stream, so close the shutter."""
    client = MagicMock()
    client.streams.add = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("custom_components.qiara.camera.asyncio.sleep", AsyncMock()), patch(
        "go2rtc_client.Go2RtcRestClient", return_value=client
    ):
        assert await camera._async_srt_stream_source() is None

    mock_api.async_activate_camera.assert_awaited_once()
    mock_api.async_deactivate_camera.assert_awaited_once_with(CAMERA_NODE)


@pytest.mark.asyncio
async def test_superseded_session_does_not_close_shutter(camera, mock_api):
    """A watcher from an older session must not close a shutter a new viewer opened."""
    old_gen = await camera._async_open_shutter(CAMERA_NODE)
    await camera._async_open_shutter(CAMERA_NODE)

    await camera._async_close_shutter(CAMERA_NODE, old_gen)

    mock_api.async_deactivate_camera.assert_not_called()


@pytest.mark.asyncio
async def test_watcher_closes_shutter_when_consumers_drop(camera, mock_api):
    """The watcher closes the shutter once go2rtc reports no consumers."""
    responses = iter([1, 0, 0])
    session = MagicMock()

    def fake_get(url):
        resp = MagicMock()
        resp.json = AsyncMock(
            return_value={"s": {"consumers": [{}] * next(responses)}}
        )
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    session.get = fake_get
    gen = await camera._async_open_shutter(CAMERA_NODE)
    with patch("custom_components.qiara.camera.asyncio.sleep", AsyncMock()):
        await camera._watch_shutter(session, "http://go2rtc/", "s", CAMERA_NODE, gen)

    mock_api.async_deactivate_camera.assert_awaited_once_with(CAMERA_NODE)


@pytest.mark.asyncio
async def test_hls_url_carries_proxy_token(camera):
    """The HLS proxy URL embeds the per-run token in its path."""
    token = camera.hass.data[DOMAIN][_CAMERA_PROXY_KEY].token
    with patch(
        "custom_components.qiara.camera.get_url", return_value="http://ha.local:8123"
    ):
        url = await camera._async_hls_stream_source()

    assert url == (
        f"http://ha.local:8123/api/qiara/camera/{token}/{CAMERA_NODE}/stream/HLS_TEST.m3u8"
    )


def _proxy_request(mock_api):
    coordinator = MagicMock(spec=QiaraDataUpdateCoordinator)
    coordinator.api = mock_api
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coordinator}}
    request = MagicMock()
    request.app = {"hass": hass}
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_ok", "node_id", "file", "quality"),
    [
        (False, str(CAMERA_NODE), "HLS_TEST.m3u8", None),  # wrong token
        (True, "999", "HLS_TEST.m3u8", None),  # not the camera node
        (True, "abc", "HLS_TEST.m3u8", None),  # non-numeric node
        (True, str(CAMERA_NODE), "..", None),  # path traversal
        (True, str(CAMERA_NODE), "seg.ts", "../home"),  # traversal via quality
    ],
)
async def test_proxy_rejects_invalid_requests(mock_api, token_ok, node_id, file, quality):
    """The unauthenticated proxy only serves the camera stream with a valid token."""
    proxy = QiaraCameraStreamProxy()
    token = proxy.token if token_ok else "nope"

    resp = await proxy.get(_proxy_request(mock_api), token, node_id, file, quality)

    assert resp.status == 404
    mock_api.async_activate_camera.assert_not_called()


@pytest.mark.asyncio
async def test_reused_ha_stream_reopens_shutter(camera):
    """HA reuses its cached Stream without calling stream_source(); reopen the shutter."""
    camera.stream = MagicMock(source=f"rtsp://127.0.0.1:18554/qiara_camera_{CAMERA_NODE}")
    with patch.object(
        Camera, "async_create_stream", AsyncMock(return_value=camera.stream)
    ), patch.object(camera, "_async_srt_stream_source", AsyncMock()) as srt:
        await camera.async_create_stream()

    srt.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_ha_stream_does_not_double_open(camera):
    """On first creation stream_source() already opened the shutter."""
    camera.stream = None
    new_stream = MagicMock(source=f"rtsp://127.0.0.1:18554/qiara_camera_{CAMERA_NODE}")
    with patch.object(
        Camera, "async_create_stream", AsyncMock(return_value=new_stream)
    ), patch.object(camera, "_async_srt_stream_source", AsyncMock()) as srt:
        await camera.async_create_stream()

    srt.assert_not_awaited()
