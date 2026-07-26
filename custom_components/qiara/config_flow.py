"""Config flow for Qiara integration."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api.client import QiaraApiClient
from .const import (
    CONF_BASE_URL,
    CONF_CUSTOMER_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SECRET_KEY,
    DEFAULT_API_PORT,
    DOMAIN,
    build_base_url,
)

_LOGGER = logging.getLogger(__name__)


def _data_schema(host: str = "", port: int = DEFAULT_API_PORT, customer_id: Any = None) -> vol.Schema:
    """Build the setup/reauth/options form: host + credentials + optional port."""
    customer_field = (
        vol.Required(CONF_CUSTOMER_ID, default=customer_id)
        if customer_id is not None
        else vol.Required(CONF_CUSTOMER_ID)
    )
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            customer_field: vol.Coerce(int),
            vol.Required(CONF_SECRET_KEY): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_PORT, default=port): vol.Coerce(int),
        }
    )


def _host_port_from_entry(data: Mapping[str, Any]) -> tuple[str, int]:
    """Return (host, port) for pre-filling a form, incl. legacy base_url entries."""
    if data.get(CONF_HOST):
        return data[CONF_HOST], data.get(CONF_PORT, DEFAULT_API_PORT)
    parts = urlsplit(data.get(CONF_BASE_URL, ""))
    return parts.hostname or "", parts.port or DEFAULT_API_PORT


def _entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise a submitted form into stored entry data (host + derived base_url)."""
    host = str(user_input[CONF_HOST]).strip()
    port = int(user_input.get(CONF_PORT, DEFAULT_API_PORT))
    return {
        CONF_CUSTOMER_ID: int(user_input[CONF_CUSTOMER_ID]),
        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_BASE_URL: build_base_url(host, port),
    }


async def _validate_credentials(hass, customer_id: int, secret_key: str, base_url: str) -> None:
    """Attempt authentication and raise on failure."""
    session = async_get_clientsession(hass)
    client = QiaraApiClient(session, customer_id, secret_key, base_url)
    await client.async_validate_credentials()


class QiaraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qiara."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _entry_data(user_input)
            try:
                await _validate_credentials(
                    self.hass,
                    data[CONF_CUSTOMER_ID],
                    data[CONF_SECRET_KEY],
                    data[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara setup failed: invalid credentials for customer %s", data[CONF_CUSTOMER_ID])
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara setup")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(data[CONF_CUSTOMER_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Qiara ({data[CONF_CUSTOMER_ID]})",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication when credentials are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth credential form."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        host, port = _host_port_from_entry(entry.data)

        if user_input is not None:
            data = _entry_data(user_input)
            try:
                await _validate_credentials(
                    self.hass,
                    data[CONF_CUSTOMER_ID],
                    data[CONF_SECRET_KEY],
                    data[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara reauth failed: invalid credentials")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara reauth")
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            host, port = data[CONF_HOST], data[CONF_PORT]

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_data_schema(host, port, entry.data.get(CONF_CUSTOMER_ID)),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> QiaraOptionsFlow:
        """Return the options flow handler."""
        return QiaraOptionsFlow(config_entry)


class QiaraOptionsFlow(OptionsFlow):
    """Handle Qiara options — allows updating credentials/host post-setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        host, port = _host_port_from_entry(self._config_entry.data)

        if user_input is not None:
            data = _entry_data(user_input)
            try:
                await _validate_credentials(
                    self.hass,
                    data[CONF_CUSTOMER_ID],
                    data[CONF_SECRET_KEY],
                    data[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara options update failed: invalid credentials")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara options update")
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(self._config_entry, data=data)
                return self.async_create_entry(title="", data={})
            host, port = data[CONF_HOST], data[CONF_PORT]

        return self.async_show_form(
            step_id="init",
            data_schema=_data_schema(host, port, self._config_entry.data.get(CONF_CUSTOMER_ID)),
            errors=errors,
        )
