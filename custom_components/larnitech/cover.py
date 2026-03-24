"""Cover platform for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech.codec import BlindsState
from pylarnitech.const import (
    DEVICE_TYPE_BLINDS,
    DEVICE_TYPE_GATE,
    DEVICE_TYPE_JALOUSIE,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity


_COVER_DEVICE_CLASSES = {
    DEVICE_TYPE_BLINDS: CoverDeviceClass.BLIND,
    DEVICE_TYPE_JALOUSIE: CoverDeviceClass.SHUTTER,
    DEVICE_TYPE_GATE: CoverDeviceClass.GARAGE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech cover entities."""
    coordinator = entry.runtime_data
    entities: list[CoverEntity] = []

    for device in coordinator.devices.values():
        if device.type in _COVER_DEVICE_CLASSES:
            entities.append(LarnitechCover(coordinator, device))

    async_add_entities(entities)


class LarnitechCover(LarnitechEntity, CoverEntity):
    """Representation of a Larnitech blind/cover."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(self, coordinator, device):
        """Initialize the cover entity."""
        super().__init__(coordinator, device)
        self._attr_device_class = _COVER_DEVICE_CLASSES.get(
            device.type, CoverDeviceClass.BLIND
        )
        # Gates typically don't support position/tilt
        if device.type == DEVICE_TYPE_GATE:
            self._attr_supported_features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )

    def _decode_state(self) -> BlindsState:
        """Decode the hex state."""
        status = self.device_status
        if status is None:
            return BlindsState.from_hex("")
        return BlindsState.from_hex(status.state)

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is closed."""
        status = self.device_status
        if status is None:
            return None
        return self._decode_state().is_closed

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position (0=closed, 100=open)."""
        status = self.device_status
        if status is None:
            return None
        return self._decode_state().position_pct

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position (0=closed, 100=open)."""
        status = self.device_status
        if status is None:
            return None
        return self._decode_state().tilt_pct

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        state = BlindsState(command=0, position=250, tilt=250, raw="")
        await self.coordinator.client.set_device_status_raw(
            self._addr, state.to_hex()
        )
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        state = BlindsState(command=0, position=0, tilt=0, raw="")
        await self.coordinator.client.set_device_status_raw(
            self._addr, state.to_hex()
        )
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        current = self._decode_state()
        current.command = 0
        await self.coordinator.client.set_device_status_raw(
            self._addr, current.to_hex()
        )
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get("position", 0)
        current = self._decode_state()
        state = BlindsState(
            command=0,
            position=round(position * 250 / 100),
            tilt=current.tilt,
            raw="",
        )
        await self.coordinator.client.set_device_status_raw(
            self._addr, state.to_hex()
        )
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position."""
        tilt = kwargs.get("tilt_position", 0)
        current = self._decode_state()
        state = BlindsState(
            command=0,
            position=current.position,
            tilt=round(tilt * 250 / 100),
            raw="",
        )
        await self.coordinator.client.set_device_status_raw(
            self._addr, state.to_hex()
        )
        self.async_write_ha_state()
