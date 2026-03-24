"""Base entity for the Larnitech integration."""

from __future__ import annotations

from pylarnitech import LarnitechDevice, LarnitechDeviceStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LarnitechCoordinator


class LarnitechEntity(CoordinatorEntity[LarnitechCoordinator]):
    """Base entity for Larnitech devices.

    Entities are grouped by CAN module ID into HA devices.
    Each entity uses the API-provided name for its own display name.
    """

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

        # Entity name: use the API name (e.g., "Office BW-AC Temp")
        # With has_entity_name=True, HA displays "{device_name} {entity_name}"
        # so we use just the distinct part of the name.
        self._attr_name = device.name or device.addr

        # Group entities by CAN module into HA devices.
        # Multiple Larnitech addresses on the same module (e.g., 407:1 AC
        # and 407:30 temp sensor) become entities under one HA device.
        module_id = device.module_id
        module_name = self._get_module_name(coordinator, module_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
            name=module_name,
            manufacturer="Larnitech",
            model=f"Module {module_id}",
            suggested_area=device.area or None,
            via_device=(DOMAIN, entry_id),
        )

    @staticmethod
    def _get_module_name(
        coordinator: LarnitechCoordinator,
        module_id: int,
    ) -> str:
        """Get a human-readable name for a CAN module.

        Uses the name of the first device on the module that has a
        meaningful name, stripping common suffixes like "Temp", "CPU".
        """
        for dev in coordinator.devices.values():
            if dev.module_id == module_id and dev.name:
                return dev.name
        return f"Module {module_id}"

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
