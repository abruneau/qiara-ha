import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aiohttp import ClientSession, ClientResponseError
from custom_components.qiara.api.client import QiaraApiClient
from homeassistant.exceptions import ConfigEntryAuthFailed

@pytest.mark.asyncio
async def test_async_get_sensors_success():
    session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.reason = "OK"
    mock_response.headers = {"Content-Type": "application/json"}
    # SDK Node fields: discarded (int), hash_t (int), id (int), type_name (str)
    # ApiNodesResponse fields: hash_i (int), list (List[Node])
    mock_response.read.return_value = b'{"hash_i": 123, "list": [{"id": 1, "type_name": "door", "discarded": 0, "hash_t": 456}]}'
    
    # Mocking the session.request context manager
    session.request.return_value.__aenter__.return_value = mock_response
    
    client = QiaraApiClient(session, "test_key", "https://api.test")
    sensors = await client.async_get_sensors()
    
    assert len(sensors) == 1
    assert sensors[0]["id"] == 1

@pytest.mark.asyncio
async def test_async_get_sensors_auth_fail():
    session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.reason = "Unauthorized"
    
    session.request.return_value.__aenter__.return_value = mock_response
    
    client = QiaraApiClient(session, "wrong_key", "https://api.test")
    with pytest.raises(ConfigEntryAuthFailed):
        await client.async_get_sensors()

@pytest.mark.asyncio
async def test_retry_logic():
    session = AsyncMock(spec=ClientSession)
    
    # First response: 500
    mock_response_500 = AsyncMock()
    mock_response_500.status = 500
    mock_response_500.reason = "Internal Server Error"
    
    # Second response: 200
    mock_response_200 = AsyncMock()
    mock_response_200.status = 200
    mock_response_200.reason = "OK"
    mock_response_200.headers = {"Content-Type": "application/json"}
    mock_response_200.read.return_value = b'{"hash_i": 123, "list": []}'
    
    session.request.return_value.__aenter__.side_effect = [mock_response_500, mock_response_200]
    
    client = QiaraApiClient(session, "test_key", "https://api.test")
    # We need to mock asyncio.sleep to avoid waiting
    import asyncio
    with patch("asyncio.sleep", return_value=None):
        sensors = await client.async_get_sensors()
        assert sensors == []
        assert session.request.call_count == 2
