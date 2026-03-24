"""Base entity for the Larnitech integration."""

from __future__ import annotations

from pylarnitech import LarnitechDevice, LarnitechDeviceStatus

from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LarnitechCoordinator


class LarnitechEntity(CoordinatorEntity[LarnitechCoordinator]):
    """Base entity for Larnitech devices.

    Entities are grouped by CAN module ID into HA devices.
    Each entity uses the API-provided name and is assigned to the
    correct HA area based on the Larnitech area field.

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
        self._larnitech_area = device.area or None
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
        model_name = self._get_module_model(coordinator, module_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
            name=model_name or f"Module {module_id}",
            manufacturer="Larnitech",
            model=model_name or f"Module {module_id}",
            via_device=(DOMAIN, entry_id),
        )

    @staticmethod
    def _get_module_model(
        coordinator: LarnitechCoordinator,
        module_id: int,
    ) -> str | None:
        """Extract the module model name from system sensor names.

        System sensors at address XX:98 or XX:97 have names like
        "DW-010 Temperature" or "BW-AC CPU". The model is the prefix
        before "Temperature", "Temp", "CPU", "Voltage", or "Current".
        """
        suffixes = (
            " Temperature", " Temp", " CPU", " Voltage", " Current",
        )
        for dev in coordinator.devices.values():
            if dev.module_id != module_id or dev.area != "System":
                continue
            for suffix in suffixes:
                if suffix in dev.name:
                    return dev.name.split(suffix)[0].strip()
        return None

    async def async_added_to_hass(self) -> None:
        """Assign entity to the correct HA area after registration."""
        await super().async_added_to_hass()
        if not self._larnitech_area:
            return

        # Look up or create the HA area matching the Larnitech area name
        area_reg = ar.async_get(self.hass)
        area = area_reg.async_get_area_by_name(self._larnitech_area)
        if area is None:
            area = area_reg.async_create(self._larnitech_area)

        # Assign this entity to that area (overrides device area)
        ent_reg = er.async_get(self.hass)
        if self.entity_id and area:
            entry = ent_reg.async_get(self.entity_id)
            if entry and entry.area_id != area.id:
                ent_reg.async_update_entity(
                    self.entity_id, area_id=area.id
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
