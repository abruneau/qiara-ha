"""Config flow for Qiara integration."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api.client import QiaraApiClient
from .const import CONF_BASE_URL, CONF_CUSTOMER_ID, CONF_SECRET_KEY, DEFAULT_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CUSTOMER_ID): vol.Coerce(int),
        vol.Required(CONF_SECRET_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    }
)


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
            try:
                await _validate_credentials(
                    self.hass,
                    int(user_input[CONF_CUSTOMER_ID]),
                    user_input[CONF_SECRET_KEY],
                    user_input[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara setup failed: invalid credentials for customer %s", user_input[CONF_CUSTOMER_ID])
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara setup")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user_input[CONF_CUSTOMER_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Qiara ({user_input[CONF_CUSTOMER_ID]})",
                    data={
                        CONF_CUSTOMER_ID: int(user_input[CONF_CUSTOMER_ID]),
                        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                        CONF_BASE_URL: user_input[CONF_BASE_URL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
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

        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    int(user_input[CONF_CUSTOMER_ID]),
                    user_input[CONF_SECRET_KEY],
                    user_input[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara reauth failed: invalid credentials")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara reauth")
                errors["base"] = "cannot_connect"
            else:
                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_CUSTOMER_ID: int(user_input[CONF_CUSTOMER_ID]),
                        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                        CONF_BASE_URL: user_input[CONF_BASE_URL],
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> QiaraOptionsFlow:
        """Return the options flow handler."""
        return QiaraOptionsFlow(config_entry)


class QiaraOptionsFlow(OptionsFlow):
    """Handle Qiara options — allows updating credentials post-setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    int(user_input[CONF_CUSTOMER_ID]),
                    user_input[CONF_SECRET_KEY],
                    user_input[CONF_BASE_URL],
                )
            except ConfigEntryAuthFailed:
                _LOGGER.warning("Qiara options update failed: invalid credentials")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Qiara options update")
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        CONF_CUSTOMER_ID: int(user_input[CONF_CUSTOMER_ID]),
                        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                        CONF_BASE_URL: user_input[CONF_BASE_URL],
                    },
                )
                return self.async_create_entry(title="", data={})

        current = self._config_entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_CUSTOMER_ID, default=current.get(CONF_CUSTOMER_ID)): vol.Coerce(int),
                vol.Required(CONF_SECRET_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_BASE_URL, default=current.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
