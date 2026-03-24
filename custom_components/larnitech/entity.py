"""Base entity for the Larnitech integration."""

from __future__ import annotations

from pylarnitech import LarnitechDevice, LarnitechDeviceStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LarnitechCoordinator


class LarnitechEntity(CoordinatorEntity[LarnitechCoordinator]):
    """Base entity for Larnitech devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LarnitechCoordinator,
        device: LarnitechDevice,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._addr = device.addr

        # Unique ID: {entry_id}_{device_addr}[_{suffix}]
        entry_id = coordinator.config_entry.entry_id
        uid = f"{entry_id}_{device.addr}"
        if unique_id_suffix:
            uid = f"{uid}_{unique_id_suffix}"
        self._attr_unique_id = uid

        # Each Larnitech device address is its own HA device.
        # The API provides a unique name per address (e.g., "Office AC",
        # "Office BW-AC Temp", "Office BW-AC CPU").
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{device.addr}")},
            name=device.name or f"Device {device.addr}",
            manufacturer="Larnitech",
            model=device.type,
            suggested_area=device.area or None,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data for this device."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._addr in self.coordinator.data
        )

    @property
    def device_status(self) -> LarnitechDeviceStatus | None:
        """Return the current status for this device."""
        return self.coordinator.get_status(self._addr)
