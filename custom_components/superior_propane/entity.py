"""Base entity class for Superior Propane integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SuperiorPropaneDataUpdateCoordinator


class SuperiorPropaneEntity(CoordinatorEntity[SuperiorPropaneDataUpdateCoordinator]):
    """Base entity class for Superior Propane sensors."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize a Superior Propane entity."""
        super().__init__(coordinator)
        self._tank_id: str = tank_data["tank_id"]
        self._tank_name: str = tank_data["tank_name"]
        self._tank_size: str = tank_data["tank_size"]
        self._tank_serial_number: str = tank_data["tank_serial_number"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"tank_{self._tank_id}")},
            name=self._tank_name,
            manufacturer="Superior Propane",
            model=f"Propane Tank ({self._tank_size} L)",
            serial_number=self._tank_serial_number,
        )

    def _get_tank_data(self) -> dict[str, Any] | None:
        """Retrieve current tank data from coordinator by tank_id."""
        if not self.coordinator.data or "tanks" not in self.coordinator.data:
            return None

        # Optimization: Use dictionary lookup if tanks are indexed by tank_id
        tanks = self.coordinator.data.get("tanks", [])
        tank_dict = {tank.get("tank_id"): tank for tank in tanks if isinstance(tank, dict)}
        return tank_dict.get(self._tank_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes or {}
        if self.coordinator.last_update_success:
            attrs["last_update"] = self.coordinator.last_successful_update_time.isoformat() if self.coordinator.last_successful_update_time else "Unknown"
        else:
            attrs["last_update"] = "Using stale data due to temporary API issue"
        return attrs