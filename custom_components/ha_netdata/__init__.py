from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from .sensor import NetdataData
from .const import DOMAIN, CONF_FILTERS

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    config = entry.data
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    filters = [ res.split("/") for res in config.get(CONF_FILTERS,[])]
    netdata = NetdataData(hass, host, port, filters)
    await netdata.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = netdata

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if len(hass.config_entries.async_entries(DOMAIN)) == 0:
            hass.data.pop(DOMAIN)
    
    return unload_ok
