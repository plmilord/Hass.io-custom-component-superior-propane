"""Custom types for Superior Propane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import SuperiorPropaneApiClient
    from .coordinator import SuperiorPropaneDataUpdateCoordinator


type SuperiorPropaneConfigEntry = ConfigEntry[SuperiorPropaneData]


@dataclass
class SuperiorPropaneData:
    """Data for the Superior Propane integration."""

    client: SuperiorPropaneApiClient
    coordinator: SuperiorPropaneDataUpdateCoordinator
    integration: Integration