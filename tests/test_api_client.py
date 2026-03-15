import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession
from custom_components.qiara.api.client import QiaraApiClient
from homeassistant.exceptions import ConfigEntryAuthFailed


@pytest.mark.asyncio
async def test_async_get_sensors_success():
    session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.reason = "OK"
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.read.return_value = b'{"hash_i": 123, "list": [{"id": 1, "type_name": "door", "discarded": 0, "hash_t": 456}]}'

    session.request.return_value.__aenter__.return_value = mock_response

    client = QiaraApiClient(session, 1, "test_secret_key", "https://api.test")
    client._session_id = "pre_set_session"  # bypass auth

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

    client = QiaraApiClient(session, 1, "test_secret_key", "https://api.test")
    client._session_id = "expired_session"

    # Re-auth also fails (persistent 401)
    with patch.object(client, "_authenticate", side_effect=ConfigEntryAuthFailed("Auth failed")):
        with pytest.raises(ConfigEntryAuthFailed):
            await client.async_get_sensors()


@pytest.mark.asyncio
async def test_retry_logic():
    session = AsyncMock(spec=ClientSession)

    mock_500 = AsyncMock()
    mock_500.status = 500
    mock_500.reason = "Internal Server Error"

    mock_200 = AsyncMock()
    mock_200.status = 200
    mock_200.reason = "OK"
    mock_200.headers = {"Content-Type": "application/json"}
    mock_200.read.return_value = b'{"hash_i": 123, "list": []}'

    session.request.return_value.__aenter__.side_effect = [mock_500, mock_200]

    client = QiaraApiClient(session, 1, "test_secret_key", "https://api.test")
    client._session_id = "pre_set_session"  # bypass auth

    with patch("asyncio.sleep", return_value=None):
        sensors = await client.async_get_sensors()
        assert sensors == []
        assert session.request.call_count == 2


@pytest.mark.asyncio
async def test_authenticate():
    session = AsyncMock(spec=ClientSession)

    challenge_resp = AsyncMock()
    challenge_resp.status = 200
    challenge_resp.reason = "OK"
    challenge_resp.headers = {}
    challenge_resp.read.return_value = b'{"challenge": "dGVzdA=="}'  # base64("test")

    session_resp = AsyncMock()
    session_resp.status = 200
    session_resp.reason = "OK"
    session_resp.headers = {}
    session_resp.read.return_value = b'{"session": "abc123"}'

    session.request.return_value.__aenter__.side_effect = [challenge_resp, session_resp]

    client = QiaraApiClient(session, 42, "dGVzdA==", "https://api.test")
    await client._authenticate()

    assert client._session_id == "abc123"
