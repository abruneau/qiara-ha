"""Client for Qiara API using the openapi_client SDK with async support."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed

from openapi_client import ApiClient, Configuration, DefaultApi
from openapi_client.exceptions import ApiException
from openapi_client.rest import RESTResponse

_LOGGER = logging.getLogger(__name__)

class AsyncRESTResponse:
    """Async version of SDK's RESTResponse."""
    def __init__(self, status, reason, data, headers):
        self.status = status
        self.reason = reason
        self.data = data
        self.headers = headers
    
    def read(self):
        """No-op for async as data is already read."""
        return self.data

class QiaraAsyncApiClient(ApiClient):
    """Async version of SDK's ApiClient using aiohttp."""
    
    def __init__(self, session: ClientSession, configuration=None):
        super().__init__(configuration)
        self.session = session

    async def async_call_api(
        self,
        method,
        url,
        header_params=None,
        body=None,
        post_params=None,
        _request_timeout=None
    ) -> AsyncRESTResponse:
        """Asynchronous replacement for call_api with retries."""
        import asyncio
        for attempt in range(3):
            try:
                async with self.session.request(
                    method,
                    url,
                    headers=header_params,
                    json=body if isinstance(body, dict) else None,
                    data=body if not isinstance(body, dict) else None,
                    timeout=_request_timeout
                ) as response:
                    status = response.status
                    reason = response.reason
                    data = await response.read()
                    headers = response.headers
                    
                    if status == 401:
                        raise ConfigEntryAuthFailed("Invalid API key")
                    
                    if status >= 500:
                        if attempt == 2:
                            response.raise_for_status()
                        wait = 2 ** attempt
                        _LOGGER.warning("Server error, retrying in %ds: %d", wait, status)
                        await asyncio.sleep(wait)
                        continue
                        
                    return AsyncRESTResponse(status, reason, data, headers)
            except Exception as err:
                if isinstance(err, ConfigEntryAuthFailed):
                    raise
                if attempt == 2:
                    _LOGGER.error("Error calling Qiara API after 3 attempts: %s", err)
                    raise ApiException(status=0, reason=str(err)) from err
                wait = 2 ** attempt
                _LOGGER.warning("Connection error, retrying in %ds: %s", wait, err)
                await asyncio.sleep(wait)
                continue


class QiaraApiClient:
    """Qiara API client wrapping the openapi_client SDK."""

    def __init__(self, session: ClientSession, api_key: str, base_url: str = "https://api.qiara.com") -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key
        self._base_url = base_url
        
        # Configure SDK
        self.config = Configuration(
            host=base_url,
            # We use SessionAuth for the x-hlcore-session-id header
            api_key={"SessionAuth": api_key},
        )
        self.api_client = QiaraAsyncApiClient(session, self.config)
        self.default_api = DefaultApi(self.api_client)

    async def async_get_sensors(self) -> list[dict[str, Any]]:
        """Get all sensors using SDK's get_nodes serialization."""
        try:
            # 1. Use SDK's internal serialize method to get request params
            # get_nodes expects x_hlcore_session_id
            params = self.default_api._get_nodes_serialize(
                x_hlcore_session_id=self._api_key,
                _request_auth=None,
                _content_type=None,
                _headers=None,
                _host_index=0
            )
            
            # 2. Call our async implementation
            response_data = await self.api_client.async_call_api(*params)
            
            # 3. Use SDK's deserialization logic
            # _get_nodes response_types_map: {'200': "ApiNodesResponse"}
            response_types_map = {'200': "ApiNodesResponse"}
            api_response = self.api_client.response_deserialize(
                response_data=response_data,
                response_types_map=response_types_map,
            )
            
            # Return raw list of nodes for compatibility with current models
            return api_response.data.to_dict().get("list", [])
        except ConfigEntryAuthFailed:
            raise
        except Exception as ex:
            _LOGGER.error("Failed to get sensors: %s", ex)
            raise

    async def async_get_sensor_data(self, sensor_id: str) -> dict[str, Any]:
        """Get specific sensor data."""
        # The SDK doesn't have a direct "get sensor by ID" that returns a single Node,
        # but get_nodes returns all. For now, we'll just filter from get_sensors.
        sensors = await self.async_get_sensors()
        for sensor in sensors:
            if sensor.get("id") == sensor_id:
                return sensor
        raise Exception(f"Sensor {sensor_id} not found")

    async def async_arm_system(self, mode: str) -> bool:
        """Arm the system."""
        # For now, we'll keep the direct call because the SDK's arming might be different
        # and we don't want to break functionality yet. 
        # But we use the async transport.
        url = f"{self._base_url}/system/arm"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        async with self._session.post(url, headers=headers, json={"mode": mode}) as response:
            response.raise_for_status()
        return True

    async def async_disarm_system(self) -> bool:
        """Disarm the system."""
        url = f"{self._base_url}/system/disarm"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with self._session.post(url, headers=headers) as response:
            response.raise_for_status()
        return True
