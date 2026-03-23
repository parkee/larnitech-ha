"""Remote platform for the Larnitech integration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pylarnitech.const import DEVICE_TYPE_IR_TRANSMITTER, DEVICE_TYPE_REMOTE_CONTROL
from pylarnitech.models import LarnitechIRSignal

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech remote entities."""
    coordinator = entry.runtime_data
    entities: list[RemoteEntity] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_REMOTE_CONTROL:
            signals = [
                LarnitechIRSignal.from_dict(s)
                for s in device.extra.get("sygnals", [])
            ]
            if signals:
                entities.append(
                    LarnitechRemote(coordinator, device, signals)
                )
        elif device.type == DEVICE_TYPE_IR_TRANSMITTER:
            entities.append(
                LarnitechIRTransmitter(coordinator, device)
            )

    async_add_entities(entities)


class LarnitechRemote(LarnitechEntity, RemoteEntity):
    """Representation of a Larnitech IR remote with learned signals.

    Each remote-control device has a list of pre-learned IR signals.
    Commands can be sent by signal name or numeric index.
    """

    _attr_name = None

    def __init__(
        self,
        coordinator,
        device,
        signals: list[LarnitechIRSignal],
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator, device)
        self._signals = signals
        self._signal_map: dict[str, LarnitechIRSignal] = {}
        for i, sig in enumerate(signals):
            name = sig.name or f"signal_{i}"
            self._signal_map[name] = sig

    @property
    def is_on(self) -> bool:
        """Return True (remote is always available when controller is)."""
        return True

    async def async_send_command(
        self,
        command: Iterable[str],
        **kwargs: Any,
    ) -> None:
        """Send IR commands.

        Each command string is matched against signal names or numeric indices.
        """
        for cmd in command:
            signal = self._signal_map.get(cmd)
            if signal is None:
                # Try as numeric index
                try:
                    idx = int(cmd)
                    if 0 <= idx < len(self._signals):
                        signal = self._signals[idx]
                except ValueError:
                    pass
            if signal is not None:
                await self.coordinator.client.send_ir_signal(
                    signal.transmitter_addr,
                    signal.value,
                )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on (no-op for IR remote)."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (no-op for IR remote)."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return available signal names."""
        return {
            "signal_count": len(self._signals),
            "signals": list(self._signal_map.keys()),
        }


class LarnitechIRTransmitter(LarnitechEntity, RemoteEntity):
    """Representation of a Larnitech IR transmitter hardware module.

    Allows sending arbitrary raw IR hex codes to a specific
    room's IR blaster. Useful for automations that send raw IR
    codes from external databases (e.g., Broadlink, IRDB).

    send_command accepts raw hex strings directly.
    """

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return True (transmitter is always available)."""
        return True

    async def async_send_command(
        self,
        command: Iterable[str],
        **kwargs: Any,
    ) -> None:
        """Send raw IR hex codes through this transmitter.

        Each command is a raw hex string representing an IR signal.
        """
        for hex_signal in command:
            await self.coordinator.client.set_device_status_raw(
                self._addr, hex_signal
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on (no-op for IR transmitter)."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (no-op for IR transmitter)."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return transmitter info."""
        return {
            "device_type": "ir_transmitter",
            "area": self._device.area,
        }
