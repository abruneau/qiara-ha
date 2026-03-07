"""The Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .api import QiaraApi

_LOGGER = logging.getLogger(__name__)

# List of platforms to support
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qiara from a config entry."""
    # Store the API instance in hass.data
    hass.data.setdefault(DOMAIN, {})

    # Create the API instance
    api = QiaraApi(
        hass.helpers.aiohttp_client.async_get_clientsession(),
        entry.data["api_key"],
        entry.data.get("base_url", "https://api.qiara.com")
    )

    # Create the coordinator
    coordinator = QiaraDataUpdateCoordinator(hass, api, entry)

    # Store coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove entry from hass.data
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)