"""Button platform for the Larnitech integration."""

from __future__ import annotations

from pylarnitech.admin import LarnitechAdminClient
from pylarnitech.const import DEVICE_TYPE_SCRIPT

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
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

        model_name = module_info.get("model", "")
        if model_name:
            device_name = f"{model_name} ({module_id})"
        else:
            device_name = f"Module {module_id}"

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
