"""Tests for QiaraApi."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from custom_components.qiara.api import QiaraApi


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
