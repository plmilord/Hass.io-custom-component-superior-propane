"""DataUpdateCoordinator for Superior Plus Propane."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientError,
)
from .const import GALLONS_TO_CUBIC_FEET, LOGGER

STORAGE_VERSION = 1
STORAGE_KEY = "superior_plus_propane_consumption"

# Consumption tracking constants
MIN_CONSUMPTION_GALLONS = 0.5  # Minimum realistic consumption per reading
MAX_CONSUMPTION_GALLONS = 10.0  # Maximum realistic consumption per reading

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SuperiorPlusPropaneConfigEntry


class SuperiorPlusPropaneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: SuperiorPlusPropaneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SuperiorPlusPropaneConfigEntry,
    ) -> None:
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
        self._previous_readings: dict[str, float] = {}
        self._consumption_totals: dict[str, float] = {}
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

    def _process_tank_consumption(self, tank: dict[str, Any]) -> None:
        """Process consumption tracking for a single tank."""
        tank_id = tank["tank_id"]
        current_gallons_str = tank.get("current_gallons", "0")

        # Convert to float, handle "unknown" values
        try:
            current_gallons = float(current_gallons_str)
        except (ValueError, TypeError):
            return

        # Calculate consumption if we have a previous reading
        if tank_id in self._previous_readings:
            previous_gallons = self._previous_readings[tank_id]
            consumption_gallons = previous_gallons - current_gallons

            # Only count realistic consumption per reading
            if (
                MIN_CONSUMPTION_GALLONS
                <= consumption_gallons
                <= MAX_CONSUMPTION_GALLONS
            ):
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

        # Calculate consumption rate (ft³/hour) with improved time tracking
        if (
            tank_id in self._consumption_totals
            and self._consumption_totals[tank_id] > 0
        ):
            # Use a simplified average rate calculation
            # For low usage scenarios, this provides a reasonable estimate
            # Rate = total consumption / 24 hours (daily average)
            tank["consumption_rate"] = round(self._consumption_totals[tank_id] / 24, 4)
        else:
            tank["consumption_rate"] = 0.0

        # Calculate days since last delivery
        last_delivery = tank.get("last_delivery", "unknown")
        if last_delivery != "unknown":
            try:
                delivery_date = datetime.strptime(last_delivery, "%m/%d/%Y").replace(
                    tzinfo=UTC
                )
                current_date = datetime.now(UTC)
                days_since = (current_date - delivery_date).days
                tank["days_since_delivery"] = days_since
            except ValueError:
                tank["days_since_delivery"] = "unknown"
        else:
            tank["days_since_delivery"] = "unknown"

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        try:
            tanks_data = (
                await self.config_entry.runtime_data.client.async_get_tanks_data()
            )

            # Process each tank for consumption tracking
            for tank in tanks_data:
                self._process_tank_consumption(tank)

            # Save consumption data to storage
            await self.async_save_consumption_data()

        except SuperiorPlusPropaneApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except SuperiorPlusPropaneApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return tanks_data
