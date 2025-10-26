"""Sensor platform for Superior Propane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
    UnitOfVolume,
)

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CURRENCY_PER_LITER, DOMAIN, LOGGER
from .entity import SuperiorPropaneEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .coordinator import SuperiorPropaneDataUpdateCoordinator
    from .data import SuperiorPropaneConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: SuperiorPropaneConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Wait for first data fetch to discover tanks
    if not coordinator.data or "tanks" not in coordinator.data:
        LOGGER.warning("No tank data available during sensor setup")
        return

    entities = []

    for tank_data in coordinator.data["tanks"]:
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
                SuperiorPropaneVolumeSensor(coordinator, tank_data),
                # Information sensors
                SuperiorPropaneLastSmartTankUpdateSensor(coordinator, tank_data),
                SuperiorPropaneLastDeliverySensor(coordinator, tank_data),
                SuperiorPropaneDaysSinceDeliverySensor(coordinator, tank_data),
                # Consumption sensors for energy dashboard
                SuperiorPropaneConsumptionTotalSensor(coordinator, tank_data),
                SuperiorPropaneConsumptionRateSensor(coordinator, tank_data),
                SuperiorPropaneAveragePriceSensor(coordinator, tank_data),
                # Data quality sensor
                SuperiorPropaneDataQualitySensor(coordinator, tank_data),
            ]
        )

    async_add_entities(entities)


class SuperiorPropaneLevelSensor(SuperiorPropaneEntity, SensorEntity):
    """Tank level percentage sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_level"
        self._attr_name = "Level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> int | None:
        """Return the current tank level percentage."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        level_str = tank_data.get("level", "Unknown")
        if level_str == "Unknown":
            return None

        try:
            return int(float(level_str))
        except (ValueError, TypeError):
            return None


class SuperiorPropaneVolumeSensor(SuperiorPropaneEntity, SensorEntity):
    """Current volume sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_current_volume"
        self._attr_name = "Current Volume"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.VOLUME
        self._attr_state_class = None
        self._attr_icon = "mdi:propane-tank"

    @property
    def native_value(self) -> float | None:
        """Return the current volume in tank."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        volume_str = tank_data.get("current_volume", "Unknown")
        if volume_str == "Unknown":
            return None

        try:
            return float(volume_str)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneLastSmartTankUpdateSensor(SuperiorPropaneEntity, SensorEntity):
    """Reading date sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_last_reading"
        self._attr_name = "Last SMART Tank Update"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        """Return the reading date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        last_reading = tank_data.get("last_reading", "Unknown")
        return None if last_reading == "Unknown" else last_reading


class SuperiorPropaneLastDeliverySensor(SuperiorPropaneEntity, SensorEntity):
    """Last delivery date sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_last_delivery"
        self._attr_name = "Last Delivery"
        self._attr_icon = "mdi:truck-delivery"

    @property
    def native_value(self) -> str | None:
        """Return the last delivery date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        delivery_date = tank_data.get("last_delivery", "Unknown")
        return None if delivery_date == "Unknown" else delivery_date


class SuperiorPropaneDaysSinceDeliverySensor(SuperiorPropaneEntity, SensorEntity):
    """Days since last delivery sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_days_since_delivery"
        self._attr_name = "Days Since Delivery"
        self._attr_native_unit_of_measurement = UnitOfTime.DAYS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:calendar-today"

    @property
    def native_value(self) -> int | None:
        """Return days since last delivery."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        days_since = tank_data.get("days_since_delivery", "Unknown")
        if days_since == "Unknown":
            return None

        try:
            return int(days_since)
        except (ValueError, TypeError):
            return None


class SuperiorPropaneConsumptionTotalSensor(SuperiorPropaneEntity, SensorEntity):
    """Total consumption sensor for energy dashboard."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_consumption_total"
        self._attr_name = "Total Consumption"
        self._attr_native_unit_of_measurement = "m³"
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:fire"

    @property
    def native_value(self) -> float | None:
        """Return total consumption in cubic meter."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_total", 0.0)


class SuperiorPropaneConsumptionRateSensor(SuperiorPropaneEntity, SensorEntity):
    """Consumption rate sensor showing current hourly usage (informational only).

    Note: This sensor is NOT used by the Energy Dashboard. The Energy Dashboard
    calculates its own rates from the Total Consumption sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_consumption_rate"
        self._attr_name = "Consumption Rate"
        self._attr_native_unit_of_measurement = "m³/h"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> float | None:
        """Return consumption rate in cubic meter per hour."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_rate", 0.0)


class SuperiorPropaneDataQualitySensor(SuperiorPropaneEntity, SensorEntity):
    """Data quality indicator sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_data_quality"
        self._attr_name = "Data Quality"
        self._attr_state_class = None
        self._attr_icon = "mdi:shield-check"

    @property
    def native_value(self) -> str | None:
        """Return the data quality status."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        quality = tank_data.get("data_quality", "Unknown")
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
            attrs["correction_reason"] = "Liters value adjusted to match tank level percentage"
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

        quality = tank_data.get("data_quality", "Unknown")
        has_correction = tank_data.get("data_corrected", False)

        if quality == "Good" and not has_correction:
            return "mdi:shield-check"
        elif quality == "data_inconsistent" or has_correction:
            return "mdi:shield-alert"
        elif quality in ["invalid_level", "invalid_tank_size", "calculation_error"]:
            return "mdi:shield-off"
        else:
            return "mdi:shield-outline"


class SuperiorPropaneAveragePriceSensor(SuperiorPropaneEntity, SensorEntity):
    """Average price paid sensor."""

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = f"{DOMAIN}_{tank_data['customer_number']}_{tank_data['tank_id']}_average_price"
        self._attr_name = "Average Price Paid"
        self._attr_native_unit_of_measurement = CURRENCY_PER_LITER
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = None
        self._attr_icon = "mdi:cash-multiple"

    @property
    def native_value(self) -> float | None:
        """Return the average price per liter, rounded to two decimal places."""
        orders_data = self.coordinator.data.get("orders") if self.coordinator.data else None
        if orders_data:
            price = orders_data.get("average_price")
            if price is not None:
                return round(price, 2)
        return None