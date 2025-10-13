"""SuperiorPropaneEntity class."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SuperiorPropaneDataUpdateCoordinator


class SuperiorPropaneEntity(
    CoordinatorEntity[SuperiorPropaneDataUpdateCoordinator]
):
    """SuperiorPropaneEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SuperiorPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._tank_id = tank_data["tank_id"]
        self._tank_address = tank_data["address"]

        # Create device info for each tank
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"tank_{self._tank_id}"),
            },
            name=f"Propane Tank - {self._tank_address}",
            manufacturer="Superior Propane",
            model="Propane Tank",
            sw_version="1.0",
        )

    def _get_tank_data(self) -> dict[str, Any] | None:
        """Get current tank data from coordinator."""
        if not self.coordinator.data:
            return None

        for tank in self.coordinator.data:
            if isinstance(tank, dict) and tank.get("tank_id") == self._tank_id:
                return tank
        return None
