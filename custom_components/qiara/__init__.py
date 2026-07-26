"""The Qiara integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_BASE_URL, DOMAIN
from .coordinator import QiaraDataUpdateCoordinator
from .api import QiaraApi

_LOGGER = logging.getLogger(__name__)

# List of platforms to support
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.ALARM_CONTROL_PANEL,
    Platform.CAMERA,
]

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry formats."""
    _LOGGER.debug("Migrating Qiara config entry from version %s", entry.version)

    if "api_key" in entry.data:
        _LOGGER.error(
            "Qiara config entry uses the old 'api_key' format which is no longer supported. "
            "Please remove and re-add the Qiara integration to supply your Customer ID and Secret Key."
        )
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qiara from a config entry."""
    # Store the API instance in hass.data
    hass.data.setdefault(DOMAIN, {})

    # Create the API instance
    api = QiaraApi(
        async_get_clientsession(hass),
        int(entry.data["customer_id"]),
        entry.data["secret_key"],
        entry.data.get("base_url", DEFAULT_BASE_URL),
    )

    # Create the coordinator
    coordinator = QiaraDataUpdateCoordinator(hass, api, entry)

    # Store coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data — raises ConfigEntryNotReady on failure so HA retries
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)