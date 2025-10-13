"""Sensor platform for Superior Propane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CURRENCY_DOLLAR,
    PERCENTAGE,
    UnitOfTime,
    UnitOfVolume,
)

from .const import DOMAIN, LOGGER
from .entity import SuperiorPropaneEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SuperiorPropaneDataUpdateCoordinator
    from .data import SuperiorPropaneConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: SuperiorPropaneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Wait for first data fetch to discover tanks
    if not coordinator.data:
        LOGGER.warning("No tank data available during sensor setup")
        return

    entities = []

    for tank_data in coordinator.data:
        if not isinstance(tank_data, dict):
            continue

        tank_id = tank_data.get("tank_id")
        address = tank_data.get("address")

        if not tank_id or not address:
            continue

        # Create all sensors for this tank
        entities.extend(
            [
                # Primary tank sensors
                SuperiorPropaneLevelSensor(coordinator, tank_data),
                SuperiorPropaneGallonsSensor(coordinator, tank_data),
                SuperiorPropaneCapacitySensor(coordinator, tank_data),
                # Information sensors
                SuperiorPropaneReadingDateSensor(coordinator, tank_data),
                SuperiorPropaneLastDeliverySensor(coordinator, tank_data),
                SuperiorPropaneDaysSinceDeliverySensor(coordinator, tank_data),
                # Consumption sensors for energy dashboard
                SuperiorPropaneConsumptionTotalSensor(coordinator, tank_data),
                SuperiorPropaneConsumptionRateSensor(coordinator, tank_data),
                # Data quality sensor
                SuperiorPropaneDataQualitySensor(coordinator, tank_data),
            ]
        )

    async_add_entities(entities)


class SuperiorPropaneLevelSensor(SuperiorPropaneEntity, SensorEntity):
    """Tank level percentage sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_level"
        self._attr_name = "Level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return the current tank level percentage."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        level_str = tank_data.get("level", "unknown")
        if level_str == "unknown":
            return None

        try:
            return float(level_str)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneGallonsSensor(SuperiorPropaneEntity, SensorEntity):
    """Current gallons sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_gallons"
        self._attr_name = "Current Gallons"
        self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS
        self._attr_device_class = SensorDeviceClass.VOLUME
        self._attr_state_class = None
        self._attr_icon = "mdi:propane-tank"

    @property
    def native_value(self) -> float | None:
        """Return the current gallons in tank."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        gallons_str = tank_data.get("current_gallons", "unknown")
        if gallons_str == "unknown":
            return None

        try:
            return float(gallons_str)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneCapacitySensor(SuperiorPropaneEntity, SensorEntity):
    """Tank capacity sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_capacity"
        self._attr_name = "Capacity"
        self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS
        self._attr_device_class = SensorDeviceClass.VOLUME
        self._attr_state_class = None
        self._attr_icon = "mdi:propane-tank-outline"

    @property
    def native_value(self) -> float | None:
        """Return the tank capacity."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        capacity_str = tank_data.get("tank_size", "unknown")
        if capacity_str == "unknown":
            return None

        try:
            return float(capacity_str)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneReadingDateSensor(SuperiorPropaneEntity, SensorEntity):
    """Reading date sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_reading_date"
        self._attr_name = "Reading Date"
        self._attr_device_class = None
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        """Return the reading date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        reading_date = tank_data.get("reading_date", "unknown")
        return None if reading_date == "unknown" else reading_date


class SuperiorPropaneLastDeliverySensor(SuperiorPropaneEntity, SensorEntity):
    """Last delivery date sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_last_delivery"
        self._attr_name = "Last Delivery"
        self._attr_device_class = None
        self._attr_icon = "mdi:truck-delivery"

    @property
    def native_value(self) -> str | None:
        """Return the last delivery date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        delivery_date = tank_data.get("last_delivery", "unknown")
        return None if delivery_date == "unknown" else delivery_date


class SuperiorPropaneDaysSinceDeliverySensor(
    SuperiorPropaneEntity, SensorEntity
):
    """Days since last delivery sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_days_since_delivery"
        self._attr_name = "Days Since Delivery"
        self._attr_native_unit_of_measurement = UnitOfTime.DAYS
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:calendar-today"

    @property
    def native_value(self) -> int | None:
        """Return days since last delivery."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        days_since = tank_data.get("days_since_delivery", "unknown")
        if days_since == "unknown":
            return None

        try:
            return int(days_since)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneConsumptionTotalSensor(
    SuperiorPropaneEntity, SensorEntity
):
    """Total consumption sensor for energy dashboard."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_consumption_total"
        self._attr_name = "Total Consumption"
        self._attr_native_unit_of_measurement = "ft³"
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:fire"

    @property
    def native_value(self) -> float | None:
        """Return total consumption in cubic feet."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_total", 0.0)


class SuperiorPropaneConsumptionRateSensor(SuperiorPropaneEntity, SensorEntity):
    """Consumption rate sensor showing current hourly usage (informational only).

    Note: This sensor is NOT used by the Energy Dashboard. The Energy Dashboard
    calculates its own rates from the Total Consumption sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_consumption_rate"
        self._attr_name = "Consumption Rate"
        self._attr_native_unit_of_measurement = "ft³/h"
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> float | None:
        """Return consumption rate in cubic feet per hour."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_rate", 0.0)


class SuperiorPropaneDataQualitySensor(SuperiorPropaneEntity, SensorEntity):
    """Data quality indicator sensor."""

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['tank_id']}_data_quality"
        self._attr_name = "Data Quality"
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = "mdi:shield-check"

    @property
    def native_value(self) -> str | None:
        """Return the data quality status."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        quality = tank_data.get("data_quality", "unknown")
        return quality

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return {}

        attrs = {}
        if tank_data.get("data_corrected"):
            attrs["data_corrected"] = True
            attrs["correction_reason"] = "Gallons value adjusted to match tank level percentage"
        if tank_data.get("consumption_anomaly"):
            attrs["consumption_anomaly"] = True
            attrs["anomaly_reason"] = "Consumption exceeded expected threshold"
        if tank_data.get("refill_detected"):
            attrs["refill_detected"] = True
            attrs["refill_reason"] = "Tank level increased since last reading"

        return attrs

    @property
    def icon(self) -> str:
        """Return dynamic icon based on quality."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return "mdi:shield-off"

        quality = tank_data.get("data_quality", "unknown")
        has_correction = tank_data.get("data_corrected", False)

        if quality == "good" and not has_correction:
            return "mdi:shield-check"
        elif quality == "data_inconsistent" or has_correction:
            return "mdi:shield-alert"
        elif quality in ["invalid_level", "invalid_tank_size", "calculation_error"]:
            return "mdi:shield-off"
        else:
            return "mdi:shield-outline"
