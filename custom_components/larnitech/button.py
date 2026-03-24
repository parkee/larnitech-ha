"""Button platform for the Larnitech integration."""

from __future__ import annotations

from pylarnitech.admin import LarnitechAdminClient
from pylarnitech.const import DEVICE_TYPE_REMOTE_CONTROL, DEVICE_TYPE_SCRIPT
from pylarnitech.models import LarnitechIRSignal

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import LarnitechConfigEntry, LarnitechCoordinator
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
        elif device.type == DEVICE_TYPE_REMOTE_CONTROL:
            # Create a button per learned IR signal
            signals = [
                LarnitechIRSignal.from_dict(s)
                for s in device.extra.get("sygnals", [])
            ]
            for i, sig in enumerate(signals):
                entities.append(
                    LarnitechIRSignalButton(
                        coordinator, device, sig, i
                    )
                )

    # Add reboot buttons for each module that has serial info
    entry_id = entry.entry_id
    host = entry.data[CONF_HOST]
    for module_id, info in coordinator.module_info.items():
        serial_dec = info.get("serial_dec", "")
        if serial_dec:
            entities.append(
                LarnitechModuleRebootButton(
                    entry_id=entry_id,
                    host=host,
                    module_id=module_id,
                    module_info=info,
                )
            )

    async_add_entities(entities)


class LarnitechScriptButton(LarnitechEntity, ButtonEntity):
    """Representation of a Larnitech script trigger."""

    async def async_press(self) -> None:
        """Trigger the script."""
        await self.coordinator.client.set_device_status_raw(
            self._addr, "ff"
        )


class LarnitechIRSignalButton(ButtonEntity):
    """Button to send a learned IR signal.

    Each learned signal on a remote-control device becomes a button.
    Users can rename "Signal 0", "Signal 1" etc. to meaningful names
    like "Power", "Volume Up" in the HA UI.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LarnitechCoordinator,
        device,
        signal: LarnitechIRSignal,
        index: int,
    ) -> None:
        """Initialize the IR signal button."""
        self._coordinator = coordinator
        self._signal = signal
        entry_id = coordinator.config_entry.entry_id

        self._attr_name = (
            f"{signal.name or f'Signal {index}'} ({device.addr})"
        )
        # Use hash of IR signal value as stable unique ID.
        # Index-based IDs would break when signals are added/deleted
        # (all subsequent signals would shift).
        import hashlib

        sig_hash = hashlib.md5(
            signal.value.encode()
        ).hexdigest()[:8]
        self._attr_unique_id = (
            f"{entry_id}_{device.addr}_ir_{sig_hash}"
        )

        module_id = device.module_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

    async def async_press(self) -> None:
        """Send the IR signal."""
        await self._coordinator.client.send_ir_signal(
            self._signal.transmitter_addr,
            self._signal.value,
        )


class LarnitechModuleRebootButton(ButtonEntity):
    """Button to reboot a Larnitech CAN bus module."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Reboot"

    def __init__(
        self,
        entry_id: str,
        host: str,
        module_id: str,
        module_info: dict[str, str],
    ) -> None:
        """Initialize the reboot button."""
        self._host = host
        self._module_id = module_id
        self._serial_dec = module_info.get("serial_dec", "")
        self._attr_unique_id = f"{entry_id}_{module_id}_reboot"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

    async def async_press(self) -> None:
        """Reboot the module."""
        admin = LarnitechAdminClient(host=self._host)
        try:
            await admin.login()
            await admin.reboot_module(self._module_id, self._serial_dec)
            LOGGER.info("Rebooted module %s", self._module_id)
        except Exception:
            LOGGER.exception("Failed to reboot module %s", self._module_id)
        finally:
            await admin.close()
