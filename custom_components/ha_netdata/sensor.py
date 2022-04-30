"""Support gathering system information of hosts which are running netdata."""
from __future__ import annotations

from datetime import timedelta
import logging
import numpy as np
from collections import deque

from netdata import Netdata
from netdata.exceptions import NetdataError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_RESOURCES,
    PERCENTAGE,
    DATA_RATE_MEGABYTES_PER_SECOND
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)
NETDATA_UPDATE_INTERVAL = timedelta(seconds=1)


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
    resources = [ res.split("/") for res in config[CONF_RESOURCES]]
    netdata = hass.data[DOMAIN][entry.entry_id]

    if netdata.api.metrics is None:
        raise PlatformNotReady

    dev: list[SensorEntity] = []
    for [sensor, element] in resources:
        sensor_name = f"{sensor} {element}"
        try:
            resource_data = netdata.api.metrics[sensor]
            unit = (
                PERCENTAGE
                if resource_data["units"] == "percentage"
                else resource_data["units"]
            )
        except KeyError:
            _LOGGER.error("Sensor is not available: %s", sensor)
            continue

        unique_id = f"netdata-{host}-{port}-{sensor}-{element}"
        dev.append(
            NetdataSensor(
                netdata, unique_id, name, sensor, sensor_name, element, unit
            )
        )

    dev.append(NetdataAlarms(netdata, name, host, port))
    async_add_entities(dev, True)


class NetdataSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Netdata sensor."""

    def __init__(self, netdata, unique_id, name, sensor, sensor_name, element, unit):
        """Initialize the Netdata sensor."""
        super().__init__(netdata)
        self.netdata = netdata
        self._unique_id = unique_id
        self._state = None
        self._sensor = sensor
        self._element = element
        self._sensor_name = self._sensor if sensor_name is None else sensor_name
        self._name = name
        self._unit_of_measurement = unit
        self._icon = "mdi:chart-line"

        if "net." in self._sensor:
            if "received" in self._element:
                self._icon = "mdi:download"
            elif "sent" in self._element:
                self._icon = "mdi:upload"
    
    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit_of_measurement == "kilobits/s":
            return DATA_RATE_MEGABYTES_PER_SECOND
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_value(self):
        """Return the state of the resources."""
        value = self.netdata.async_get_resource(self._sensor, self._element)
        if self._unit_of_measurement == "kilobits/s":
            return round(value / 1024 / 8, 3)

        return value


class NetdataAlarms(CoordinatorEntity, SensorEntity):
    """Implementation of a Netdata alarm sensor."""

    def __init__(self, netdata, name, host, port):
        """Initialize the Netdata alarm sensor."""
        super().__init__(netdata)
        self.netdata = netdata
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
        alarms = self.netdata.api.alarms["alarms"]
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

    def __init__(self, hass, host, port, filters):
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=NETDATA_UPDATE_INTERVAL
        )
        self.api = Netdata(host, port=port)
        self.filters = filters
        
        self.cache = {}
        for sensor,element in self.filters:
            self.cache[(sensor,element)] = deque(maxlen= 3)
    
    async def _async_update_data(self):
        await self.api.get_allmetrics()
        await self.api.get_alarms()

        for [sensor,element] in self.filters:
            resource_data = self.api.metrics.get(sensor)
            self.cache[(sensor,element)].append(abs(resource_data["dimensions"][element]["value"]))
        return self.api
    
    def async_get_resource(self, sensor, element):
        if values:=self.cache.get((sensor, element)):
            avg = np.mean(values)
            return round(avg,2)

        resource_data = self.api.metrics.get(sensor)
        return round(abs(resource_data["dimensions"][element]["value"]), 2)

        
