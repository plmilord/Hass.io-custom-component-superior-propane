"""SuperiorPlusPropaneEntity class."""

from __future__ import annotations

from typing import Any, Dict

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator


class SuperiorPlusPropaneEntity(
    CoordinatorEntity[SuperiorPlusPropaneDataUpdateCoordinator]
):
    """SuperiorPlusPropaneEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: Dict[str, Any],
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
            manufacturer="Superior Plus Propane",
            model="Propane Tank",
            sw_version="1.0",
        )

    def _get_tank_data(self) -> Dict[str, Any] | None:
        """Get current tank data from coordinator."""
        if not self.coordinator.data:
            return None

        for tank in self.coordinator.data:
            if isinstance(tank, dict) and tank.get("tank_id") == self._tank_id:
                return tank
        return None
