"""Custom types for Superior Plus Propane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import SuperiorPlusPropaneApiClient
    from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator


type SuperiorPlusPropaneConfigEntry = ConfigEntry[SuperiorPlusPropaneData]


@dataclass
class SuperiorPlusPropaneData:
    """Data for the Superior Plus Propane integration."""

    client: SuperiorPlusPropaneApiClient
    coordinator: SuperiorPlusPropaneDataUpdateCoordinator
    integration: Integration
