"""Custom integration to integrate Superior Propane with Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import SuperiorPropaneApiClient
from .coordinator import SuperiorPropaneDataUpdateCoordinator
from .data import SuperiorPropaneData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .data import SuperiorPropaneConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: SuperiorPropaneConfigEntry) -> bool:
    """Set up this integration using UI."""
    coordinator = SuperiorPropaneDataUpdateCoordinator(hass=hass, config_entry=entry)

    entry.runtime_data = SuperiorPropaneData(
        client=SuperiorPropaneApiClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=async_create_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # Load stored consumption data before first refresh
    await coordinator.async_load_consumption_data()

    # Perform first refresh to populate coordinator.data
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SuperiorPropaneConfigEntry) -> bool:
    """Handle removal of an entry."""
    # Close the dedicated session to clean up resources
    if entry.runtime_data and entry.runtime_data.client:
        session = getattr(entry.runtime_data.client, "_session", None)
        if session and hasattr(session, "close"):
            await session.close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SuperiorPropaneConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)