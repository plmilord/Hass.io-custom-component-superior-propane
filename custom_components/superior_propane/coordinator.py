"""DataUpdateCoordinator for Superior Propane."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SuperiorPropaneApiClientAuthenticationError,
    SuperiorPropaneApiClientError,
)
from .const import (
    ABSOLUTE_MAX_CONSUMPTION,
    ABSOLUTE_MIN_CONSUMPTION,
    DATA_VALIDATION_TOLERANCE,
    DEFAULT_MAX_CONSUMPTION_LITERS,
    DEFAULT_MIN_CONSUMPTION_LITERS,
    LITERS_TO_CUBIC_METERS,
    LOGGER,
    MAX_CONSUMPTION_PERCENTAGE,
    MIN_CONSUMPTION_PERCENTAGE,
    PERCENT_MULTIPLIER,
    SECONDS_PER_HOUR,
    TANK_SIZE_MAX,
    TANK_SIZE_MIN,
)

STORAGE_VERSION = 1
STORAGE_KEY = "superior_propane_consumption"

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SuperiorPropaneConfigEntry


class SuperiorPropaneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: SuperiorPropaneConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SuperiorPropaneConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Superior Propane",
            update_interval=timedelta(
                seconds=config_entry.data.get("update_interval", 3600)
            ),
        )
        self.account_data: dict[str, Any] = {}
        self.config_entry = config_entry
        self._previous_readings: dict[str, float] = {}
        self._consumption_totals: dict[str, float] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data_quality_flags: dict[str, str] = {}
        self._use_dynamic_thresholds = config_entry.data.get("adaptive_thresholds", True)
        self._min_threshold_override = config_entry.data.get("min_consumption_threshold")
        self._max_threshold_override = config_entry.data.get("max_consumption_threshold")

    async def async_load_consumption_data(self) -> None:
        """Load consumption data from storage with migration support."""
        stored_data = await self._store.async_load()
        if stored_data:
            # Check if migration is needed from v1 to v2
            stored_version = stored_data.get("version", 1)  # v1 didn't have version field

            if stored_version == 1:
                # Migrate from v1 to v2 format
                LOGGER.info("Migrating consumption data from v1 to v2 format")
                # v1 format had same structure, just add version marker
                stored_data["version"] = STORAGE_VERSION
                await self._store.async_save(stored_data)

            self._consumption_totals = stored_data.get("consumption_totals", {})
            self._previous_readings = stored_data.get("previous_readings", {})
            LOGGER.debug("Loaded consumption data: %s", self._consumption_totals)

    async def async_save_consumption_data(self) -> None:
        """Save consumption data to storage."""
        data = {
            "version": STORAGE_VERSION,
            "consumption_totals": self._consumption_totals,
            "previous_readings": self._previous_readings,
            "last_updated": datetime.now(UTC).isoformat(),
        }
        await self._store.async_save(data)
        LOGGER.debug("Saved consumption data: %s", self._consumption_totals)

    def _calculate_dynamic_thresholds(self, tank_size: float, update_interval_hours: float) -> tuple[float, float]:
        """Calculate dynamic consumption thresholds based on tank size and update interval."""
        # Use overrides if BOTH are provided
        if (self._min_threshold_override is not None and self._max_threshold_override is not None):
            return self._min_threshold_override, self._max_threshold_override

        # Use individual overrides with dynamic calculation for the other
        if (self._min_threshold_override is not None or self._max_threshold_override is not None):
            if self._use_dynamic_thresholds:
                # Calculate dynamic values
                min_dynamic = (tank_size * MIN_CONSUMPTION_PERCENTAGE * update_interval_hours)
                max_dynamic = (tank_size * MAX_CONSUMPTION_PERCENTAGE * update_interval_hours)
                min_dynamic = max(ABSOLUTE_MIN_CONSUMPTION, min_dynamic)
                max_dynamic = min(ABSOLUTE_MAX_CONSUMPTION, max_dynamic)

                # Use override if provided, otherwise use dynamic
                min_threshold = (
                    self._min_threshold_override
                    if self._min_threshold_override is not None
                    else min_dynamic
                )
                max_threshold = (
                    self._max_threshold_override
                    if self._max_threshold_override is not None
                    else max_dynamic
                )
                return min_threshold, max_threshold
            else:
                # Use overrides with defaults for missing values
                return (
                    (
                        self._min_threshold_override
                        if self._min_threshold_override is not None
                        else DEFAULT_MIN_CONSUMPTION_LITERS
                    ),
                    (
                        self._max_threshold_override
                        if self._max_threshold_override is not None
                        else DEFAULT_MAX_CONSUMPTION_LITERS
                    ),
                )

        if not self._use_dynamic_thresholds:
            return DEFAULT_MIN_CONSUMPTION_LITERS, DEFAULT_MAX_CONSUMPTION_LITERS

        # Dynamic calculation based on tank size
        min_consumption = tank_size * MIN_CONSUMPTION_PERCENTAGE * update_interval_hours
        max_consumption = tank_size * MAX_CONSUMPTION_PERCENTAGE * update_interval_hours

        # Apply absolute bounds for safety
        min_consumption = max(ABSOLUTE_MIN_CONSUMPTION, min_consumption)
        max_consumption = min(ABSOLUTE_MAX_CONSUMPTION, max_consumption)

        return min_consumption, max_consumption

    def _validate_tank_data(self, tank: dict[str, Any]) -> bool:
        """Validate tank data consistency and set quality flags."""
        tank_id = tank.get("tank_id", "Unknown")

        # Validate tank size
        try:
            tank_size = float(tank.get("tank_size", 0))
            if not (TANK_SIZE_MIN <= tank_size <= TANK_SIZE_MAX):
                LOGGER.warning("Tank %s has unrealistic size: %s liters", tank_id, tank_size)
                self._data_quality_flags[tank_id] = "invalid_tank_size"
                return False
        except (ValueError, TypeError):
            self._data_quality_flags[tank_id] = "invalid_tank_size"
            return False

        # Validate level percentage
        try:
            level = float(tank.get("level", -1))
            if not (0 <= level <= 100):
                LOGGER.warning("Tank %s has invalid level: %s%%", tank_id, level)
                self._data_quality_flags[tank_id] = "invalid_level"
                return False
        except (ValueError, TypeError):
            self._data_quality_flags[tank_id] = "invalid_level"
            return False

        # Validate consistency between level% and liters
        try:
            current_volume = float(tank.get("current_volume", 0))
            expected_liters = ((level * tank_size) / PERCENT_MULTIPLIER if tank_size > 0 else 0)

            if tank_size > 0 and expected_liters > 0:
                variance = abs(current_volume - expected_liters) / tank_size
                if variance > DATA_VALIDATION_TOLERANCE:
                    LOGGER.warning(
                        "Tank %s data inconsistency: Level %s%% suggests %.1f liters, "
                        "but scraped value is %.1f liters (tank size: %.0f, variance: %.1f%%)",
                        tank_id,
                        level,
                        expected_liters,
                        current_volume,
                        tank_size,
                        variance * 100,
                    )
                    self._data_quality_flags[tank_id] = "data_inconsistent"
                    # Use calculated value as it's more reliable
                    tank["current_volume"] = str(expected_liters)
                    tank["data_corrected"] = True
                else:
                    self._data_quality_flags[tank_id] = "Good"
        except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
            self._data_quality_flags[tank_id] = "calculation_error"
            return False

        return True

    def _process_tank_consumption(self, tank: dict[str, Any]) -> None:
        """Process consumption tracking for a single tank."""
        tank_id = tank.get("tank_id")
        if not tank_id:
            LOGGER.warning("Tank data missing tank_id, skipping consumption processing")
            return

        # Validate tank data first
        if not self._validate_tank_data(tank):
            LOGGER.debug("Tank %s data validation failed", tank_id)
            tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)
            tank["consumption_rate"] = 0.0
            tank["data_quality"] = self._data_quality_flags.get(tank_id, "Unknown")
            return

        current_volume_str = tank.get("current_volume", "0")

        # Convert to float, handle "Unknown" values
        try:
            current_volume = float(current_volume_str)
            tank_size = float(tank.get("tank_size", 500))  # Default to 500 if missing
        except (ValueError, TypeError):
            tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)
            tank["consumption_rate"] = 0.0
            tank["data_quality"] = "invalid_data"
            return

        # Calculate dynamic thresholds
        update_interval_hours = max(0.001, self.update_interval.total_seconds() / SECONDS_PER_HOUR)  # Prevent division by zero
        min_threshold, max_threshold = self._calculate_dynamic_thresholds(tank_size, update_interval_hours)

        # Calculate consumption if we have a previous reading
        if tank_id in self._previous_readings:
            previous_liters = self._previous_readings[tank_id]
            consumption_liters = previous_liters - current_volume

            # Handle tank refills (negative consumption)
            if consumption_liters < 0:
                # Tank was refilled - log but don't count as consumption
                try:
                    if tank_size > 0:
                        LOGGER.info(
                            "Tank %s was refilled: %.2f -> %.2f liters (%.1f%% -> %.1f%%)",
                            tank_id,
                            previous_liters,
                            current_volume,
                            (previous_liters / tank_size) * PERCENT_MULTIPLIER,
                            (current_volume / tank_size) * PERCENT_MULTIPLIER,
                        )
                    else:
                        LOGGER.info(
                            "Tank %s was refilled: %.2f -> %.2f liters",
                            tank_id,
                            previous_liters,
                            current_volume,
                        )
                except (ZeroDivisionError, ArithmeticError):
                    LOGGER.info(
                        "Tank %s was refilled: %.2f -> %.2f liters",
                        tank_id,
                        previous_liters,
                        current_volume,
                    )
                tank["refill_detected"] = True
            # Check against dynamic thresholds
            elif consumption_liters > 0:
                # Convert liters to cubic meters and add to total
                consumption_m3 = consumption_liters * LITERS_TO_CUBIC_METERS

                if tank_id not in self._consumption_totals:
                    self._consumption_totals[tank_id] = 0.0

                # Log based on threshold validation
                if consumption_liters < min_threshold:
                    LOGGER.info(
                        "Tank %s low consumption: %.3f liters (%.4f m³) [below threshold: %.3f]",
                        tank_id,
                        consumption_liters,
                        consumption_m3,
                        min_threshold,
                    )
                    # Still record it for accuracy
                    self._consumption_totals[tank_id] += consumption_m3
                elif consumption_liters > max_threshold:
                    LOGGER.warning(
                        "Tank %s high consumption: %.2f liters (%.3f m³) [above threshold: %.2f] - recording with anomaly flag",
                        tank_id,
                        consumption_liters,
                        consumption_m3,
                        max_threshold,
                    )
                    # Record but flag as anomaly
                    self._consumption_totals[tank_id] += consumption_m3
                    tank["consumption_anomaly"] = True
                else:
                    # Normal consumption
                    self._consumption_totals[tank_id] += consumption_m3
                    LOGGER.debug(
                        "Tank %s consumed %.2f liters (%.3f m³). Total: %.3f m³",
                        tank_id,
                        consumption_liters,
                        consumption_m3,
                        self._consumption_totals[tank_id],
                    )

        # Store actual previous reading BEFORE updating for rate calculation
        actual_previous = self._previous_readings.get(tank_id)

        # Update previous reading
        self._previous_readings[tank_id] = current_volume

        # Add consumption total to tank data for Energy Dashboard
        # This is the TOTAL_INCREASING value that Home Assistant uses
        tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)

        # Calculate instantaneous consumption rate based on last reading interval
        # This is for informational purposes only - Energy Dashboard doesn't use this
        if actual_previous is not None and update_interval_hours > 0:
            consumption_liters = actual_previous - current_volume

            if consumption_liters > 0:
                try:
                    consumption_m3 = consumption_liters * LITERS_TO_CUBIC_METERS
                    tank["consumption_rate"] = round(consumption_m3 / update_interval_hours, 4)
                except (ZeroDivisionError, ArithmeticError):
                    LOGGER.warning("Error calculating consumption rate for tank %s", tank_id)
                    tank["consumption_rate"] = 0.0
            else:
                tank["consumption_rate"] = 0.0
        else:
            tank["consumption_rate"] = 0.0

        # Add data quality indicator
        tank["data_quality"] = self._data_quality_flags.get(tank_id, "Unknown")

        # Calculate days since last delivery
        last_delivery = tank.get("last_delivery", "Unknown")
        if last_delivery != "Unknown":
            try:
                delivery_date = datetime.strptime(last_delivery, "%m/%d/%Y").replace(tzinfo=UTC)
                current_date = datetime.now(UTC)
                days_since = (current_date - delivery_date).days
                tank["days_since_delivery"] = days_since
            except (ValueError, TypeError):
                tank["days_since_delivery"] = "Unknown"
        else:
            tank["days_since_delivery"] = "Unknown"

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        try:
            tanks_data = await self.config_entry.runtime_data.client.async_get_tanks_data()
            LOGGER.debug("Raw tank data from API: %s", json.dumps(tanks_data, indent=2))

            # Process each tank for consumption tracking
            for tank in tanks_data:
                try:
                    self._process_tank_consumption(tank)
                    tank_id = tank.get("tank_id")
                    if tank_id and self._data_quality_flags.get(tank_id) != "Good":
                        LOGGER.info("Tank %s data quality: %s", tank_id, self._data_quality_flags.get(tank_id, "Unknown"))
                except Exception as processing_error:
                    LOGGER.error("Error processing tank data: %s - Continuing with other tanks", processing_error, exc_info=True)

            # Fetch and compute orders totals (account-wide)
            orders_totals = await self.config_entry.runtime_data.client.async_get_orders_totals()
            total_litres = orders_totals.get("total_litres", 0.0)
            total_cost = orders_totals.get("total_cost", 0.0)
            average_price = total_cost / total_litres if total_litres > 0 else 0.0
            self.account_data = {
                "total_litres": total_litres,
                "total_cost": total_cost,
                "average_price": average_price,
            }

            # Save consumption data...
            await self.async_save_consumption_data()

            return tanks_data

        except SuperiorPropaneApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except SuperiorPropaneApiClientError as exception:
            raise UpdateFailed(exception) from exception