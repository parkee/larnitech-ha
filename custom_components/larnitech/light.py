"""Light platform for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech.const import DEVICE_TYPE_DIMMER_LAMP, DEVICE_TYPE_LAMP

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
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
    """Set up Larnitech light entities."""
    coordinator = entry.runtime_data
    entities: list[LightEntity] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_LAMP:
            entities.append(LarnitechLight(coordinator, device))
        elif device.type == DEVICE_TYPE_DIMMER_LAMP:
            entities.append(LarnitechDimmerLight(coordinator, device))

    async_add_entities(entities)


class LarnitechLight(LarnitechEntity, LightEntity):
    """Representation of a Larnitech on/off light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        status = self.device_status
        if status is None:
            return None
        return status.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "on"}
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "off"}
        )
        await self.coordinator.async_request_refresh()


class LarnitechDimmerLight(LarnitechEntity, LightEntity):
    """Representation of a Larnitech dimmable light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        status = self.device_status
        if status is None:
            return None
        return status.state == "on"

    @property
    def brightness(self) -> int | None:
        """Return the brightness 0-255."""
        status = self.device_status
        if status is None:
            return None
        larnitech_brightness = status.brightness
        if larnitech_brightness is None:
            return None
        # Larnitech: 0-100, HA: 0-255
        return round(larnitech_brightness * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        cmd: dict[str, Any] = {"state": "on"}
        if ATTR_BRIGHTNESS in kwargs:
            # HA: 0-255, Larnitech: 0-100
            cmd["brightness"] = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
        await self.coordinator.client.set_device_status(self._addr, cmd)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.client.set_device_status(
            self._addr, {"state": "off"}
        )
        await self.coordinator.async_request_refresh()
