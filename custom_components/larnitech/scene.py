"""Scene platform for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech.const import DEVICE_TYPE_LIGHT_SCHEME

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech scene entities."""
    coordinator = entry.runtime_data
    entities: list[Scene] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_LIGHT_SCHEME:
            entities.append(LarnitechScene(coordinator, device))

    async_add_entities(entities)


class LarnitechScene(LarnitechEntity, Scene):
    """Representation of a Larnitech light scheme."""


    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "on"}
        )
