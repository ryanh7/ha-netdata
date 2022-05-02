"""Support gathering system information of hosts which are running netdata."""
from __future__ import annotations

from datetime import timedelta
import logging

from netdata import Netdata

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCES,
    PERCENTAGE,
    DATA_RATE_MEGABYTES_PER_SECOND,
    TEMP_CELSIUS,
    POWER_WATT
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Netdata sensor."""
    config = entry.data
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    resources = config[CONF_RESOURCES]
    coordinator = hass.data[DOMAIN][entry.entry_id]

    dev: list[SensorEntity] = []
    for res in resources:
        [sensor, element] = res.split("/")
        unique_id = f"netdata-{host}-{port}-{sensor}-{element}"
        dev.append(
            NetdataSensor(
                coordinator, unique_id, name, sensor, element
            )
        )

    dev.append(NetdataAlarms(coordinator, name, host, port))
    async_add_entities(dev, True)


class NetdataSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Netdata sensor."""

    def __init__(self, coordinator, unique_id, name, sensor, element):
        """Initialize the Netdata sensor."""
        super().__init__(coordinator)
        self._unique_id = unique_id
        self._state = None
        self._sensor = sensor
        self._element = element
        self._name = name
        
        unit = self.coordinator.data.metrics[self._sensor]["units"]
        self._unit_lower = str(unit).lower()
        if self._unit_lower == "kilobits/s":
            self._unit_of_measurement = DATA_RATE_MEGABYTES_PER_SECOND
        elif self._unit_lower == "percentage":
            self._unit_of_measurement = PERCENTAGE
        elif self._unit_lower == "watts":
            self._unit_of_measurement = POWER_WATT
        elif self._unit_lower == "celsius":
            self._unit_of_measurement = TEMP_CELSIUS
        else:
            self._unit_of_measurement = unit
        
        self._icon = "mdi:chart-line"
        if "net." in self._sensor:
            if "received" in self._element:
                self._icon = "mdi:download"
            elif "sent" in self._element:
                self._icon = "mdi:upload"
        if self._unit_lower == "celsius":
            self._icon = "mdi:thermometer"
        elif self._unit_lower == "watts":
            self._icon = "mdi:lightning-bolt"

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor} {self._element}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_value(self):
        """Return the state of the resources."""
        resource_data = self.coordinator.data.metrics.get(self._sensor)
        value = round(
            abs(resource_data["dimensions"][self._element]["value"]), 2)

        if self._unit_lower == "kilobits/s":
            return round(value / 1024 / 8, 3)

        return value


class NetdataAlarms(CoordinatorEntity, SensorEntity):
    """Implementation of a Netdata alarm sensor."""

    def __init__(self, coordinator, name, host, port):
        """Initialize the Netdata alarm sensor."""
        super().__init__(coordinator)
        self._state = None
        self._name = name
        self._host = host
        self._port = port

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Alarms"

    @property
    def native_value(self):
        """Return the state of the resources."""
        alarms = self.coordinator.data.alarms["alarms"]
        self._state = None
        number_of_alarms = len(alarms)
        number_of_relevant_alarms = number_of_alarms

        _LOGGER.debug("Host %s has %s alarms", self.name, number_of_alarms)

        for alarm in alarms:
            if alarms[alarm]["recipient"] == "silent":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "CLEAR":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "UNDEFINED":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "UNINITIALIZED":
                number_of_relevant_alarms = number_of_relevant_alarms - 1
            elif alarms[alarm]["status"] == "CRITICAL":
                self._state = "critical"
                return
        self._state = "ok" if number_of_relevant_alarms == 0 else "warning"
        return self._state

    @property
    def icon(self):
        """Status symbol if type is symbol."""
        if self._state == "ok":
            return "mdi:check"
        if self._state == "warning":
            return "mdi:alert-outline"
        if self._state == "critical":
            return "mdi:alert"
        return "mdi:crosshairs-question"


class NetdataData(DataUpdateCoordinator):
    """The class for handling the data retrieval."""

    def __init__(self, hass, host, port, interval):
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval)
        )
        self.api = Netdata(host, port=port)

    async def _async_update_data(self):
        await self.api.get_allmetrics()
        await self.api.get_alarms()

        return self.api
