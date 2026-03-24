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

    Supports optimistic state updates via _pending_status: after sending
    a command, the pending status is used for property reads until the
    coordinator delivers a real update from the controller.
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
        self._pending_status: LarnitechDeviceStatus | None = None

        # Unique ID: {entry_id}_{device_addr}[_{suffix}]
        entry_id = coordinator.config_entry.entry_id
        uid = f"{entry_id}_{device.addr}"
        if unique_id_suffix:
            uid = f"{uid}_{unique_id_suffix}"
        self._attr_unique_id = uid

        # Entity name: use the API name (e.g., "Office BW-AC Temp")
        self._attr_name = device.name or device.addr

        # Group entities by CAN module into HA devices.
        module_id = device.module_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
            name=f"Module {module_id}",
            manufacturer="Larnitech",
            model=f"Module {module_id}",
            suggested_area=device.area or None,
            via_device=(DOMAIN, entry_id),
        )

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data update — clear pending status."""
        self._pending_status = None
        super()._handle_coordinator_update()

    def _set_pending_status(self, state: str, **extra: object) -> None:
        """Set an optimistic pending status after a command.

        This ensures that property reads return the commanded state
        immediately, avoiding the on-off-on flicker when the real
        status arrives from the controller a moment later.
        """
        self._pending_status = LarnitechDeviceStatus(
            addr=self._addr,
            type=self._device.type,
            state=state,
            extra=dict(extra),
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
        """Return the current status, preferring pending optimistic state."""
        if self._pending_status is not None:
            return self._pending_status
        return self.coordinator.get_status(self._addr)
