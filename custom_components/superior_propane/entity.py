"""SuperiorPropaneEntity class."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SuperiorPropaneDataUpdateCoordinator


class SuperiorPropaneEntity(CoordinatorEntity[SuperiorPropaneDataUpdateCoordinator]):
    """SuperiorPropaneEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: SuperiorPropaneDataUpdateCoordinator, tank_data: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._tank_id = tank_data["tank_id"]
        self._tank_name = tank_data["tank_name"]
        self._tank_size = tank_data["tank_size"]
        self._tank_serial_number = tank_data["tank_serial_number"]

        # Create device info for each tank
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"tank_{self._tank_id}")},
            name=f"{self._tank_name}",
            manufacturer="Superior Propane",
            model=f"Propane Tank ({self._tank_size} L)",
            serial_number=f"{self._tank_serial_number}",
        )

    def _get_tank_data(self) -> dict[str, Any] | None:
        """Get current tank data from coordinator."""
        if not self.coordinator.data:
            return None

        for tank in self.coordinator.data:
            if isinstance(tank, dict) and tank.get("tank_id") == self._tank_id:
                return tank
        return None