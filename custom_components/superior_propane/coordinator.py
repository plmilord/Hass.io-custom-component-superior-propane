"""DataUpdateCoordinator for Superior Propane."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SuperiorPropaneApiClientCommunicationError,
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
    RETRY_INTERVAL,
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
                seconds=config_entry.data.get("update_interval", 7200)
            ),
        )
        self._normal_interval = timedelta(seconds=config_entry.data.get("update_interval", 7200))
        self._retry_interval = timedelta(seconds=RETRY_INTERVAL)
        self.update_interval = self._normal_interval  # Start with normal interval
        self.orders_data: dict[str, Any] = {}
        self.config_entry = config_entry
        self._previous_readings: dict[str, float] = {}
        self._consumption_totals: dict[str, float] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data_quality_flags: dict[str, str] = {}
        self._use_dynamic_thresholds = config_entry.data.get("adaptive_thresholds", True)
        self._min_threshold_override = config_entry.data.get("min_consumption_threshold")
        self._max_threshold_override = config_entry.data.get("max_consumption_threshold")
        self.last_successful_update_time: datetime | None = None

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
                variance = abs(current_volume - expected_liters) / expected_liters
                if variance > DATA_VALIDATION_TOLERANCE:
                    LOGGER.warning(
                        "Tank %s inconsistent data: %.2f liters vs expected %.2f (%.2f%%) - variance %.2f%%",
                        tank_id,
                        current_volume,
                        expected_liters,
                        level,
                        variance * 100,
                    )
                    self._data_quality_flags[tank_id] = "inconsistent_values"
                    return False
        except (ValueError, TypeError, ZeroDivisionError):
            self._data_quality_flags[tank_id] = "inconsistent_values"
            return False

        # If all checks pass
        self._data_quality_flags[tank_id] = "Good"
        return True

    def _process_tank_consumption(self, tank: dict[str, Any]) -> None:
        """Process tank data for consumption calculation."""
        tank_id = tank.get("tank_id", "Unknown")
        if not self._validate_tank_data(tank):
            LOGGER.warning("Skipping consumption calculation for tank %s due to invalid data", tank_id)
            return

        try:
            current_volume = float(tank.get("current_volume", 0))
            tank_size = float(tank.get("tank_size", 0))
        except (ValueError, TypeError):
            LOGGER.warning("Invalid volume or size for tank %s, skipping consumption", tank_id)
            return

        update_interval_hours = self.update_interval.total_seconds() / SECONDS_PER_HOUR
        min_threshold, max_threshold = self._calculate_dynamic_thresholds(tank_size, update_interval_hours)

        previous_liters = self._previous_readings.get(tank_id, current_volume)
        consumption_liters = previous_liters - current_volume

        tank["refill_detected"] = False
        tank["consumption_anomaly"] = False

        # Handle potential refill (increase in level)
        if consumption_liters < 0:
            tank["refill_detected"] = True
            try:
                LOGGER.info(
                    "Tank %s refilled: %.2f%% (%.2f L) -> %.2f%% (%.2f L)",
                    tank_id,
                    (previous_liters / tank_size) * PERCENT_MULTIPLIER,
                    previous_liters,
                    (current_volume / tank_size) * PERCENT_MULTIPLIER,
                    current_volume,
                )
            except (ZeroDivisionError, ArithmeticError):
                LOGGER.info(
                    "Tank %s was refilled: %.2f -> %.2f liters",
                    tank_id,
                    previous_liters,
                    current_volume,
                )

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
                delivery_date = datetime.strptime(last_delivery, "%Y-%m-%d").replace(tzinfo=UTC)
                current_date = datetime.now(UTC)
                days_since = (current_date - delivery_date).days
                tank["days_since_delivery"] = days_since
            except (ValueError, TypeError):
                tank["days_since_delivery"] = "Unknown"
        else:
            tank["days_since_delivery"] = "Unknown"

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            tanks_data, orders_totals = await self.config_entry.runtime_data.client.async_get_all_data()

            # Process each tank for consumption tracking
            for tank in tanks_data:
                try:
                    self._process_tank_consumption(tank)
                    tank_id = tank.get("tank_id")
                    if tank_id and self._data_quality_flags.get(tank_id) != "Good":
                        LOGGER.info("Tank %s data quality: %s", tank_id, self._data_quality_flags.get(tank_id, "Unknown"))
                except Exception as processing_error:
                    LOGGER.error("Error processing tank data: %s", processing_error, exc_info=True)

            # Process orders totals (account-wide)
            total_litres = int(orders_totals.get("total_litres", 0))
            total_cost = round(float(orders_totals.get("total_cost", 0.0)), 2)
            total_m3 = round(total_litres * LITERS_TO_CUBIC_METERS, 2) if total_litres > 0 else 0.0
            average_price_per_m3 = round(total_cost / total_m3, 2) if total_m3 > 0 else 0.0
            self.orders_data = {
                "total_litres": total_litres,
                "total_cost": total_cost,
                "average_price": average_price_per_m3
            }

            # Save consumption data...
            await self.async_save_consumption_data()

            # Success: Switch back to normal interval
            self.update_interval = self._normal_interval
            self.last_successful_update_time = datetime.now(UTC)
            LOGGER.debug("Update successful, using normal interval: %s", self.update_interval)

            return {
                "tanks": tanks_data,
                "orders": self.orders_data
            }

        except SuperiorPropaneApiClientAuthenticationError as exception:
            self.update_interval = self._retry_interval
            LOGGER.debug("Session expired, switching to retry interval: %s", self.update_interval)
            raise UpdateFailed(f"API authentication error: {exception}") from exception

        except SuperiorPropaneApiClientCommunicationError as exception:
            if "maintenance" in str(exception).lower():
                self.update_interval = timedelta(hours=1)
                LOGGER.debug("Site under maintenance, switching to retry interval: %s", self.update_interval)
            else:
                self.update_interval = self._retry_interval
                LOGGER.debug("Temporary API issue, switching to retry interval: %s", self.update_interval)
            if self.data:
                return self.data
            else:
                raise UpdateFailed(f"API communication error: {exception}") from exception

        except SuperiorPropaneApiClientError as exception:
            self.update_interval = self._retry_interval
            LOGGER.debug("Temporary API issue, switching to retry interval: %s", self.update_interval)
            raise UpdateFailed(f"API error: {exception}") from exception

        except Exception as exception:
            # Catch-all for unexpected errors (e.g., timeout, network issues)
            self.update_interval = self._retry_interval
            LOGGER.debug("Unexpected error during update, switching to retry interval: %s", self.update_interval)
            raise UpdateFailed(f"Unexpected error: {exception}") from exception