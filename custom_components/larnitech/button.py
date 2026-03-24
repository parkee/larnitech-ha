"""Button platform for the Larnitech integration."""

from __future__ import annotations

from pylarnitech.const import DEVICE_TYPE_SCRIPT

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech button entities."""
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_SCRIPT:
            entities.append(LarnitechScriptButton(coordinator, device))

    async_add_entities(entities)


class LarnitechScriptButton(LarnitechEntity, ButtonEntity):
    """Representation of a Larnitech script trigger."""


    async def async_press(self) -> None:
        """Trigger the script."""
        await self.coordinator.client.set_device_status_raw(
            self._addr, "ff"
        )
