"""Config flow for Superior Propane integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from slugify import slugify

from .api import (
    SuperiorPropaneApiClient,
    SuperiorPropaneApiClientAuthenticationError,
    SuperiorPropaneApiClientCommunicationError,
    SuperiorPropaneApiClientError,
)
from .const import (
    CONF_ADAPTIVE_THRESHOLDS,
    CONF_MAX_THRESHOLD,
    CONF_MIN_THRESHOLD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_CONSUMPTION_LITERS,
    DEFAULT_MIN_CONSUMPTION_LITERS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
)


class SuperiorPropaneFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Superior Propane."""

    VERSION = 1

    def _get_common_schema(self, defaults: dict | None = None) -> vol.Schema:
        """Return common schema for user and reauth steps."""
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=defaults.get(CONF_USERNAME, vol.UNDEFINED),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )

    async def async_step_user(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                await self.async_set_unique_id(slugify(user_input[CONF_USERNAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Superior Propane ({user_input[CONF_USERNAME]})",
                    data={
                        **user_input,
                        CONF_UPDATE_INTERVAL: user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                        CONF_ADAPTIVE_THRESHOLDS: user_input.get(CONF_ADAPTIVE_THRESHOLDS, True),
                        CONF_MIN_THRESHOLD: user_input.get(CONF_MIN_THRESHOLD, DEFAULT_MIN_CONSUMPTION_LITERS),
                        CONF_MAX_THRESHOLD: user_input.get(CONF_MAX_THRESHOLD, DEFAULT_MAX_CONSUMPTION_LITERS),
                    },
                )
            except SuperiorPropaneApiClientAuthenticationError:
                errors["base"] = "auth"
            except SuperiorPropaneApiClientCommunicationError:
                errors["base"] = "connection"
            except SuperiorPropaneApiClientError as err:
                LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_common_schema().extend(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=DEFAULT_UPDATE_INTERVAL,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=300,
                            max=86400,
                            step=300,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_ADAPTIVE_THRESHOLDS,
                        default=True,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_MIN_THRESHOLD,
                        default=DEFAULT_MIN_CONSUMPTION_LITERS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=5.0,
                            step=0.01,
                            unit_of_measurement="liters",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_THRESHOLD,
                        default=DEFAULT_MAX_CONSUMPTION_LITERS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.0,
                            max=100.0,
                            step=1.0,
                            unit_of_measurement="liters",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Handle re-authentication flow."""
        errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                return self.async_abort(reason="reauth_successful")
            except SuperiorPropaneApiClientAuthenticationError:
                errors["base"] = "auth"
            except SuperiorPropaneApiClientCommunicationError:
                errors["base"] = "connection"
            except SuperiorPropaneApiClientError as err:
                LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth",
            data_schema=self._get_common_schema(),
            description_placeholders={"title": f"Re-authenticate Superior Propane ({self.context.get('unique_id')})"},
            errors=errors,
        )

    async def _test_credentials(self, username: str, password: str) -> None:
        """Validate credentials."""
        client = SuperiorPropaneApiClient(
            username=username,
            password=password,
        )
        if not await client.async_test_connection():
            raise SuperiorPropaneApiClientAuthenticationError("Invalid credentials")

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SuperiorPropaneOptionsFlowHandler()


class SuperiorPropaneOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Superior Propane."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.config_entry: config_entries.ConfigEntry

    async def async_step_init(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            min_threshold = user_input.get(CONF_MIN_THRESHOLD)
            max_threshold = user_input.get(CONF_MAX_THRESHOLD)
            if min_threshold is not None and max_threshold is not None and min_threshold >= max_threshold:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "invalid_thresholds"},
                )

            data = dict(self.config_entry.data)
            data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="init", data_schema=self._get_options_schema())

    def _get_options_schema(self) -> vol.Schema:
        """Get the options schema with current values."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=300,
                        max=86400,
                        step=300,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_ADAPTIVE_THRESHOLDS,
                    default=self.config_entry.data.get(CONF_ADAPTIVE_THRESHOLDS, True),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_MIN_THRESHOLD,
                    default=self.config_entry.data.get(CONF_MIN_THRESHOLD, DEFAULT_MIN_CONSUMPTION_LITERS),
                    description={"suffix": "Only used when adaptive thresholds are disabled"},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.01,
                        max=5.0,
                        step=0.01,
                        unit_of_measurement="liters",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_MAX_THRESHOLD,
                    default=self.config_entry.data.get(CONF_MAX_THRESHOLD, DEFAULT_MAX_CONSUMPTION_LITERS),
                    description={"suffix": "Only used when adaptive thresholds are disabled"},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=100.0,
                        step=1.0,
                        unit_of_measurement="liters",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )