from __future__ import annotations
from email.policy import default
import logging

import voluptuous as vol
from netdata import Netdata
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_RESOURCES

from .const import CONF_DOMAINS, DOMAIN, CONF_FILTERS

_LOGGER = logging.getLogger(__name__)


class NetdataFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            netdata = Netdata(user_input[CONF_HOST], port=user_input[CONF_PORT])
            await netdata.get_allmetrics()
            self.domains = sorted(list({ m.split(".")[0] for m in netdata.metrics}))
            self.metrics = netdata.metrics
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
            for sensor,data in self.metrics.items():
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
            self.filters = sorted(user_input[CONF_RESOURCES])
            self.config.update(user_input)
            return await self.async_step_filters()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_RESOURCES): cv.multi_select(self.sensors)
                    }
            ),
            errors=errors,
        )


    async def async_step_filters(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"netdata-{self.config[CONF_HOST]}-{self.config[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            self.config.update(user_input)
            return self.async_create_entry(title=self.config[CONF_NAME], data=self.config)

        return self.async_show_form(
            step_id="filters",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_FILTERS): cv.multi_select(self.filters)
                    }
            ),
            errors=errors,
        )

