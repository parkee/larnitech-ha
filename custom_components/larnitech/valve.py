"""Valve platform for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech.const import DEVICE_TYPE_VALVE

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech valve entities."""
    coordinator = entry.runtime_data
    entities: list[ValveEntity] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_VALVE:
            entities.append(LarnitechValve(coordinator, device))

    async_add_entities(entities)


class LarnitechValve(LarnitechEntity, ValveEntity):
    """Representation of a Larnitech water/gas valve."""

    _attr_name = None
    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )

    @property
    def is_closed(self) -> bool | None:
        """Return True if the valve is closed."""
        status = self.device_status
        if status is None:
            return None
        return status.state != "open"

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "open"}
        )
        await self.coordinator.async_request_refresh()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "closed"}
        )
        await self.coordinator.async_request_refresh()
