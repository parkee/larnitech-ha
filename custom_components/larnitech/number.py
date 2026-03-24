"""Number platform for Larnitech module pin parameters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .admin_coordinator import LarnitechAdminCoordinator
from .const import DOMAIN, LOGGER
from .coordinator import LarnitechConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech pin parameter number entities."""
    coordinator = entry.runtime_data
    admin_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    admin_coord: LarnitechAdminCoordinator | None = admin_data.get(
        "admin_coordinator"
    )
    if not admin_coord:
        return

    entry_id = entry.entry_id
    entities: list[NumberEntity] = []

    # Fetch all HW configs through the shared admin coordinator
    try:
        hw_configs = await admin_coord.fetch_all_hw_configs(
            list(coordinator.module_info.keys())
        )
    except Exception:
        LOGGER.warning("Could not fetch HW configs for pin params")
        return

    for module_id, info in coordinator.module_info.items():
        hw_config = hw_configs.get(module_id)
        if not isinstance(hw_config, dict):
            continue

        add_params = hw_config.get("addPinParams", {})
        pins_hw_list = hw_config.get("pinsHWList", {})

        if not add_params or not pins_hw_list:
            continue

        # addPinParams defines per-connector parameters:
        # {"OUT": {"runtime": {"min": 0, "max": 100, ...}}}
        # {"dm": {"min": {"min": 0, "max": 100, ...}}}
        for connector, params in add_params.items():
            if not isinstance(params, dict):
                continue
            for param_name, param_def in params.items():
                if not isinstance(param_def, dict):
                    continue
                if param_def.get("formFieldType") != "number":
                    continue

                param_min = param_def.get("min", 0)
                param_max = param_def.get("max", 100)
                label = param_def.get("label", param_name)
                # Clean up TXT_ prefix from labels
                if label.startswith("TXT_"):
                    label = (
                        label[4:]
                        .replace("_", " ")
                        .title()
                        .replace("Module Pin ", "")
                    )

                # Create a number entity per pin that has this param
                for pin_num, pin_hw in pins_hw_list.items():
                    if not isinstance(pin_hw, dict):
                        continue
                    if param_name not in pin_hw:
                        continue

                    current_val = pin_hw.get(param_name, 0)
                    try:
                        current_val = float(current_val)
                    except (ValueError, TypeError):
                        current_val = param_def.get("defaultValue", 0)

                    entities.append(
                        LarnitechPinNumber(
                            admin_coord=admin_coord,
                            entry_id=entry_id,
                            module_id=module_id,
                            connector=connector,
                            pin_num=pin_num,
                            param_name=param_name,
                            label=label,
                            min_val=param_min,
                            max_val=param_max,
                            current_val=current_val,
                        )
                    )

    async_add_entities(entities)


class LarnitechPinNumber(NumberEntity):
    """Number entity for a module pin parameter (min, max, runtime, etc)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        admin_coord: LarnitechAdminCoordinator,
        entry_id: str,
        module_id: str,
        connector: str,
        pin_num: str,
        param_name: str,
        label: str,
        min_val: float,
        max_val: float,
        current_val: float,
    ) -> None:
        """Initialize the pin parameter number."""
        self._admin_coord = admin_coord
        self._module_id = module_id
        self._connector = connector
        self._pin_num = pin_num
        self._param_name = param_name

        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_value = current_val
        self._attr_native_step = 1.0
        self._attr_name = (
            f"{label} Pin {pin_num} ({module_id})"
        )
        self._attr_unique_id = (
            f"{entry_id}_{module_id}_param_{connector}_{pin_num}_{param_name}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

        # Set unit based on param name
        if "runtime" in param_name.lower() or "hold" in param_name.lower():
            self._attr_native_unit_of_measurement = "ms"
        elif param_name in ("min", "max", "start", "force"):
            self._attr_native_unit_of_measurement = "%"

    async def async_set_native_value(self, value: float) -> None:
        """Set the parameter value."""
        # Build hw config for this single param change
        int_val = int(value)
        hw_config = (
            f"hw[{self._connector}][{self._pin_num}]"
            f"[{self._param_name}]={int_val}"
        )
        try:
            await self._admin_coord.set_hw_config(
                self._module_id, hw_config
            )
            self._attr_native_value = value
            self.async_write_ha_state()
        except Exception:
            LOGGER.exception(
                "Failed to set %s on module %s pin %s/%s",
                self._param_name,
                self._module_id,
                self._connector,
                self._pin_num,
            )
