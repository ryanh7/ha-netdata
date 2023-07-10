from __future__ import annotations
import logging
import requests
import json

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_RESOURCES, CONF_SCAN_INTERVAL

from .const import CONF_DOMAINS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NetdataFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            request_netdata = await self.hass.async_add_executor_job(
                requests.get,
                f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/api/v1/allmetrics?format=json&help=no&types=no&timestamps=yes&names=yes&data=average"
            )
            self.metrics = json.loads(request_netdata.content)
            self.domains = sorted(
                list({m.split(".")[0] for m in self.metrics}))
            self.config = user_input
            return await self.async_step_domains()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME, default="Netdata"): str,
                        vol.Required(CONF_HOST, default="localhost"): str,
                        vol.Required(CONF_PORT, default=19999): vol.Coerce(int),
                    }
            ),
            errors=errors,
        )

    async def async_step_domains(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.sensors = []
            for sensor, data in self.metrics.items():
                if sensor.split(".")[0] not in user_input[CONF_DOMAINS]:
                    continue
                for element in data["dimensions"].keys():
                    self.sensors.append(f"{sensor}/{element}")
            self.sensors = sorted(self.sensors)
            self.config.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="domains",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DOMAINS): cv.multi_select(self.domains)
                    }
            ),
            errors=errors,
        )

    async def async_step_sensors(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.config.update(user_input)
            await self.async_set_unique_id(
                f"netdata-{self.config[CONF_HOST]}-{self.config[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self.config[CONF_NAME], data=self.config)

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_RESOURCES): cv.multi_select(self.sensors),
                        vol.Required(CONF_SCAN_INTERVAL, default=1): vol.All(vol.Coerce(int), vol.Range(min=1))
                    }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.config = dict(config_entry.data)

    async def async_step_init(self, user_input=None):
        request_netdata = await self.hass.async_add_executor_job(
            requests.get,
            f"http://{self.config[CONF_HOST]}:{self.config[CONF_PORT]}/api/v1/allmetrics?format=json&help=no&types=no&timestamps=yes&names=yes&data=average"
        )
        self.metrics = json.loads(request_netdata.content)
        self.domains = sorted(
            list({m.split(".")[0] for m in self.metrics}))

        if user_input is not None:
            self.sensors = []
            for sensor, data in self.metrics.items():
                if sensor.split(".")[0] not in user_input[CONF_DOMAINS]:
                    continue
                for element in data["dimensions"].keys():
                    self.sensors.append(f"{sensor}/{element}")
            self.sensors = sorted(self.sensors)
            self.config.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DOMAINS, default=list(d for d in self.config[CONF_DOMAINS] if d in self.domains)): cv.multi_select(self.domains)
                    }
            ),
        )

    async def async_step_sensors(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.config.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.config
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=self.config)

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_RESOURCES, default=list(s for s in self.config[CONF_RESOURCES] if s in self.sensors)): cv.multi_select(self.sensors),
                        vol.Required(CONF_SCAN_INTERVAL, default=self.config[CONF_SCAN_INTERVAL]): vol.All(vol.Coerce(int), vol.Range(min=1))
                    }
            ),
            errors=errors,
        )
