"""Tests for QiaraApi."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from custom_components.qiara.api import QiaraApi, _apply_endpoints
from custom_components.qiara.models import QiaraSensorData


def _sensor(*, id="10", name="Qiara Siren 10", type="siren", **kwargs) -> QiaraSensorData:
    """Return a minimal QiaraSensorData for endpoint-mapping tests."""
    return QiaraSensorData(id=id, name=name, type=type, **kwargs)


def test_apply_endpoints_temperature_whole_degrees():
    """A reading with a real timestamp maps to whole degrees Celsius."""
    result = _apply_endpoints(
        _sensor(),
        [{"ep_name": "temperature", "value": {"timestamp": 1785001939, "value": 24}}],
    )
    assert result.temperature == 24.0


def test_apply_endpoints_temperature_sentinel_ignored():
    """A reading with timestamp 0 is a sentinel and leaves temperature unset."""
    result = _apply_endpoints(
        _sensor(),
        [{"ep_name": "temperature", "value": {"timestamp": 0, "value": 200}}],
    )
    assert result.temperature is None


def test_apply_endpoints_room_names_door_with_type():
    """A placed door node is named '<Room> Door/Window' (title-cased room, no 'Sensor' suffix)."""
    result = _apply_endpoints(
        _sensor(id="12", name="Qiara Door/Window Sensor 12", type="door"),
        [{"ep_name": "room", "value": "sous sol"}],
    )
    assert result.name == "Sous Sol Door/Window"


def test_apply_endpoints_room_names_motion_with_type():
    """A placed motion node is named '<Room> Motion'."""
    result = _apply_endpoints(
        _sensor(id="24", name="Qiara Motion Sensor 24", type="motion"),
        [{"ep_name": "room", "value": "étage"}],
    )
    assert result.name == "Étage Motion"


def test_apply_endpoints_no_room_keeps_default_name():
    """A node without a room keeps its default 'Qiara <Type> <id>' name."""
    result = _apply_endpoints(
        _sensor(id="42", name="Qiara Door/Window Sensor 42", type="door"),
        [{"ep_name": "state", "value": None}],
    )
    assert result.name == "Qiara Door/Window Sensor 42"


def test_apply_endpoints_blank_room_keeps_default_name():
    """A whitespace-only room is ignored rather than blanking the name."""
    result = _apply_endpoints(
        _sensor(id="42", name="Qiara Door/Window Sensor 42", type="door"),
        [{"ep_name": "room", "value": "   "}],
    )
    assert result.name == "Qiara Door/Window Sensor 42"


@pytest.fixture
def mock_client():
    """Return a mock QiaraApiClient."""
    client = MagicMock()
    client.async_read_endpoints = AsyncMock()
    return client


@pytest.fixture
def api(mock_client):
    """Return a QiaraApi with a mock client and pre-set alarm node id."""
    instance = QiaraApi.__new__(QiaraApi)
    instance._client = mock_client
    instance._alarm_node_id = 42
    return instance


@pytest.mark.asyncio
async def test_async_get_alarm_state_success(api, mock_client):
    """Test async_get_alarm_state returns the raw value from hl_alarm_status endpoint."""
    mock_client.async_read_endpoints.return_value = [
        {
            "node_id": 42,
            "ep_values": [{"ep_name": "hl_alarm_status", "value": "day"}],
        }
    ]

    result = await api.async_get_alarm_state()

    assert result == "day"
    mock_client.async_read_endpoints.assert_called_once_with(
        [{"node_id": 42, "eps": ["hl_alarm_status"]}]
    )


@pytest.mark.asyncio
async def test_async_get_alarm_state_no_alarm_node(api):
    """Test async_get_alarm_state returns None when alarm node not yet discovered."""
    api._alarm_node_id = None
    result = await api.async_get_alarm_state()
    assert result is None


@pytest.mark.asyncio
async def test_async_get_alarm_state_returns_night(api, mock_client):
    """Test async_get_alarm_state returns 'night' when system is armed at night."""
    mock_client.async_read_endpoints.return_value = [
        {
            "node_id": 42,
            "ep_values": [{"ep_name": "hl_alarm_status", "value": "night"}],
        }
    ]
    result = await api.async_get_alarm_state()
    assert result == "night"


@pytest.mark.asyncio
async def test_async_get_alarm_state_returns_off(api, mock_client):
    """Test async_get_alarm_state returns 'off' when system is disarmed."""
    mock_client.async_read_endpoints.return_value = [
        {
            "node_id": 42,
            "ep_values": [{"ep_name": "hl_alarm_status", "value": "off"}],
        }
    ]
    result = await api.async_get_alarm_state()
    assert result == "off"


@pytest.mark.asyncio
async def test_async_get_alarm_state_endpoint_missing(api, mock_client):
    """Test async_get_alarm_state returns None when hl_alarm_status endpoint not in response."""
    mock_client.async_read_endpoints.return_value = [
        {"node_id": 42, "ep_values": []}
    ]
    result = await api.async_get_alarm_state()
    assert result is None


@pytest.mark.asyncio
async def test_async_get_alarm_state_on_exception_returns_none(api, mock_client):
    """Test async_get_alarm_state returns None (does not raise) on client error."""
    mock_client.async_read_endpoints.side_effect = Exception("network error")
    result = await api.async_get_alarm_state()
    assert result is None
