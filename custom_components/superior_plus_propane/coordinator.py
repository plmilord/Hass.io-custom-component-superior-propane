"""DataUpdateCoordinator for Superior Plus Propane."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .api import (
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientError,
)
from .const import LOGGER, GALLONS_TO_CUBIC_FEET

STORAGE_VERSION = 1
STORAGE_KEY = "superior_plus_propane_consumption"

if TYPE_CHECKING:
    from .data import SuperiorPlusPropaneConfigEntry


class SuperiorPlusPropaneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: SuperiorPlusPropaneConfigEntry

    def __init__(self, hass, config_entry):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Superior Plus Propane",
            update_interval=timedelta(
                seconds=config_entry.data.get("update_interval", 3600)
            ),
        )
        self.config_entry = config_entry
        self._previous_readings: Dict[str, float] = {}
        self._consumption_totals: Dict[str, float] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load_consumption_data(self) -> None:
        """Load consumption data from storage."""
        stored_data = await self._store.async_load()
        if stored_data:
            self._consumption_totals = stored_data.get("consumption_totals", {})
            self._previous_readings = stored_data.get("previous_readings", {})
            LOGGER.debug("Loaded consumption data: %s", self._consumption_totals)

    async def async_save_consumption_data(self) -> None:
        """Save consumption data to storage."""
        data = {
            "consumption_totals": self._consumption_totals,
            "previous_readings": self._previous_readings,
        }
        await self._store.async_save(data)
        LOGGER.debug("Saved consumption data: %s", self._consumption_totals)

    async def _async_update_data(self) -> List[Dict[str, Any]]:
        """Update data via library."""
        try:
            tanks_data = (
                await self.config_entry.runtime_data.client.async_get_tanks_data()
            )

            # Process each tank for consumption tracking
            for tank in tanks_data:
                tank_id = tank["tank_id"]
                current_gallons_str = tank.get("current_gallons", "0")

                # Convert to float, handle "unknown" values
                try:
                    current_gallons = float(current_gallons_str)
                except (ValueError, TypeError):
                    continue

                # Calculate consumption if we have a previous reading
                if tank_id in self._previous_readings:
                    previous_gallons = self._previous_readings[tank_id]
                    consumption_gallons = previous_gallons - current_gallons

                    # Only count realistic consumption (0.1 to 15 gallons per reading)
                    if 0.1 <= consumption_gallons <= 15:
                        # Convert gallons to cubic feet and add to total
                        consumption_ft3 = consumption_gallons * GALLONS_TO_CUBIC_FEET

                        if tank_id not in self._consumption_totals:
                            self._consumption_totals[tank_id] = 0.0

                        self._consumption_totals[tank_id] += consumption_ft3

                        LOGGER.debug(
                            "Tank %s consumed %.2f gallons (%.3f ft³). Total: %.3f ft³",
                            tank_id,
                            consumption_gallons,
                            consumption_ft3,
                            self._consumption_totals[tank_id],
                        )

                # Update previous reading
                self._previous_readings[tank_id] = current_gallons

                # Add consumption total to tank data
                tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)

                # Calculate consumption rate (ft³/hour) if we have data
                if (
                    tank_id in self._consumption_totals
                    and self._consumption_totals[tank_id] > 0
                ):
                    # This is a simplified rate calculation
                    # In a real implementation, you'd track time windows
                    tank["consumption_rate"] = round(
                        self._consumption_totals[tank_id] / 24, 4
                    )
                else:
                    tank["consumption_rate"] = 0.0

                # Calculate days since last delivery
                last_delivery = tank.get("last_delivery", "unknown")
                if last_delivery != "unknown":
                    try:
                        from datetime import datetime

                        delivery_date = datetime.strptime(last_delivery, "%m/%d/%Y")
                        days_since = (datetime.now() - delivery_date).days
                        tank["days_since_delivery"] = days_since
                    except ValueError:
                        tank["days_since_delivery"] = "unknown"
                else:
                    tank["days_since_delivery"] = "unknown"

            # Save consumption data to storage
            await self.async_save_consumption_data()

            return tanks_data

        except SuperiorPlusPropaneApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except SuperiorPlusPropaneApiClientError as exception:
            raise UpdateFailed(exception) from exception
