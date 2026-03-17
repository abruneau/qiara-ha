"""Client for Qiara API using the openapi_client SDK with async support."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed

from openapi_client import ApiClient, Configuration
from openapi_client.exceptions import ApiException

from ..const import DEFAULT_BASE_URL

_LOGGER = logging.getLogger(__name__)


def _generate_hmac_response(challenge: str, key: str) -> str:
    """Compute HMAC-SHA1 challenge response for Qiara authentication."""
    key_bytes = base64.b64decode(key)
    digest = hmac.new(key_bytes, challenge.encode("utf-8"), hashlib.sha1)
    return digest.hexdigest()


class AsyncRESTResponse:
    """Minimal wrapper to satisfy SDK's response_deserialize interface."""

    def __init__(self, status: int, reason: str, data: bytes, headers: Any) -> None:
        self.status = status
        self.reason = reason
        self.data = data
        self.headers = headers

    def read(self) -> bytes:
        return self.data


class QiaraAsyncApiClient(ApiClient):
    """ApiClient subclass that uses HA's aiohttp session for async transport."""

    def __init__(self, session: ClientSession, configuration=None) -> None:
        super().__init__(configuration)
        self.session = session

    async def call_api_async(
        self,
        method: str,
        url: str,
        header_params: dict | None = None,
        body: Any = None,
        _request_timeout: Any = None,
    ) -> AsyncRESTResponse:
        """Async HTTP call with exponential backoff retries for 5xx errors."""
        for attempt in range(3):
            try:
                async with self.session.request(
                    method,
                    url,
                    headers=header_params,
                    json=body if isinstance(body, dict) else None,
                    data=body if not isinstance(body, dict) else None,
                    timeout=_request_timeout,
                    ssl=self.configuration.verify_ssl,
                ) as response:
                    status = response.status
                    reason = response.reason
                    data = await response.read()
                    headers = response.headers

                    if status == 401:
                        raise ConfigEntryAuthFailed("Session expired or invalid credentials")

                    if status >= 500:
                        if attempt == 2:
                            response.raise_for_status()
                        wait = 2**attempt
                        _LOGGER.warning("Server error %d, retrying in %ds", status, wait)
                        await asyncio.sleep(wait)
                        continue

                    return AsyncRESTResponse(status, reason, data, headers)
            except ConfigEntryAuthFailed:
                raise
            except Exception as err:
                if attempt == 2:
                    _LOGGER.error("Qiara API call failed after 3 attempts: %s", err)
                    raise ApiException(status=0, reason=str(err)) from err
                wait = 2**attempt
                _LOGGER.warning("Connection error, retrying in %ds: %s", wait, err)
                await asyncio.sleep(wait)


class QiaraApiClient:
    """Qiara API client — handles challenge/response auth and SDK calls."""

    def __init__(
        self,
        session: ClientSession,
        customer_id: int,
        secret_key: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._customer_id = customer_id
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._session_id: str | None = None

        config = Configuration(host=self._base_url)
        config.verify_ssl = False
        self._api_client = QiaraAsyncApiClient(session, config)

    async def _authenticate(self) -> None:
        """Perform challenge/response auth and cache the resulting session ID."""
        challenge_resp = await self._api_client.call_api_async(
            "GET", f"{self._base_url}/login/challenge"
        )
        challenge_str = json.loads(challenge_resp.data)["challenge"]
        hmac_response = _generate_hmac_response(challenge_str, self._secret_key)

        session_resp = await self._api_client.call_api_async(
            "POST",
            f"{self._base_url}/login/new",
            header_params={"Content-Type": "application/json"},
            body={"cust_id": self._customer_id, "challenge_rsp": hmac_response},
        )
        self._session_id = json.loads(session_resp.data)["session"]
        _LOGGER.debug("Qiara: authenticated successfully")

    async def async_validate_credentials(self) -> None:
        """Validate credentials by performing a full authentication. Raises on failure."""
        self._session_id = None
        await self._authenticate()

    async def _ensure_session(self) -> str:
        """Return a valid session ID, authenticating first if needed."""
        if not self._session_id:
            await self._authenticate()
        return self._session_id

    async def async_get_sensors(self) -> list[dict[str, Any]]:
        """Return all sensor nodes, re-authenticating once on session expiry."""
        for attempt in range(2):
            try:
                session_id = await self._ensure_session()
                response = await self._api_client.call_api_async(
                    "POST",
                    f"{self._base_url}/home/nodes",
                    header_params={
                        "x-hlcore-session-id": session_id,
                        "Content-Type": "application/json",
                    },
                    body={"hash_i": 0},
                )
                nodes_data = json.loads(response.data)
                return nodes_data.get("list", [])
            except ConfigEntryAuthFailed:
                if attempt == 0:
                    _LOGGER.warning("Qiara: session expired, re-authenticating")
                    self._session_id = None
                    continue
                raise
            except Exception as ex:
                _LOGGER.error("Failed to get sensors: %s", ex)
                raise

    async def async_get_sensor_data(self, sensor_id: str) -> dict[str, Any]:
        """Get a single sensor by ID from the full sensor list."""
        for sensor in await self.async_get_sensors():
            if str(sensor.get("id")) == sensor_id:
                return sensor
        raise KeyError(f"Sensor {sensor_id} not found")

    async def async_read_endpoints(self, items: list[dict]) -> list[dict]:
        """Read endpoint values for a list of nodes."""
        for attempt in range(2):
            try:
                session_id = await self._ensure_session()
                response = await self._api_client.call_api_async(
                    "POST",
                    f"{self._base_url}/home/endpoints_read",
                    header_params={
                        "x-hlcore-session-id": session_id,
                        "Content-Type": "application/json",
                    },
                    body={"list": items},
                )
                return json.loads(response.data).get("list", [])
            except ConfigEntryAuthFailed:
                if attempt == 0:
                    _LOGGER.warning("Qiara: session expired, re-authenticating")
                    self._session_id = None
                    continue
                raise
            except Exception as ex:
                _LOGGER.error("Failed to read endpoints: %s", ex)
                raise

    async def async_write_endpoint(self, node_id: int, ep_name: str, value: str) -> None:
        """Write a single endpoint value to a node."""
        session_id = await self._ensure_session()
        await self._api_client.call_api_async(
            "POST",
            f"{self._base_url}/home/endpoints_write",
            header_params={
                "x-hlcore-session-id": session_id,
                "Content-Type": "application/json",
            },
            body={"list": [{"node_id": node_id, "eps": [{"ep_name": ep_name, "value": value}]}]},
        )

    async def async_arm_system(self, node_id: int, mode: str) -> bool:
        """Arm the security system by writing hl_alarm_status on the alarm node."""
        await self.async_write_endpoint(node_id, "hl_alarm_status", mode)
        return True

    async def async_disarm_system(self, node_id: int) -> bool:
        """Disarm the security system by writing hl_alarm_status=off on the alarm node."""
        await self.async_write_endpoint(node_id, "hl_alarm_status", "off")
        return True
