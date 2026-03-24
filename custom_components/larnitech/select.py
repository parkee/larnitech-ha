"""Select platform for Larnitech module pin configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
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
    """Set up Larnitech pin configuration select entities."""
    coordinator = entry.runtime_data
    admin_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    admin_coord: LarnitechAdminCoordinator | None = admin_data.get(
        "admin_coordinator"
    )
    if not admin_coord:
        return

    entry_id = entry.entry_id
    entities: list[SelectEntity] = []

    # Fetch all HW configs through the shared admin coordinator
    try:
        hw_configs = await admin_coord.fetch_all_hw_configs(
            list(coordinator.module_info.keys())
        )
        LOGGER.debug("Fetched HW config for %d modules", len(hw_configs))
    except Exception:
        LOGGER.warning("Could not fetch HW configs for pin config")
        return

    for module_id, info in coordinator.module_info.items():
        model = info.get("model", "")
        hw_config = hw_configs.get(module_id)
        if not hw_config:
            continue

        if not isinstance(hw_config, dict):
            LOGGER.debug("Module %s: HW config is not a dict", module_id)
            continue

        data = hw_config.get("data", {})
        types = hw_config.get("types", {})
        hw_types = hw_config.get("hwTypes", {})

        if not data or not types:
            LOGGER.debug(
                "Module %s: no data/types (keys=%s)", module_id, list(hw_config.keys())
            )
            continue

        LOGGER.debug(
            "Module %s (%s): %d connectors, %d types",
            module_id, model, len(data), len(types),
        )

        if not data or not types:
            continue

        # Build type code → display name mapping
        # types can be a dict {code: name} or a list [name, name, ...]
        type_names: dict[str, str] = {}
        if isinstance(types, dict):
            for code, name in types.items():
                if isinstance(name, str):
                    display = name.replace("TYPE_", "").replace("TXT_", "").replace("_", " ").title()
                    type_names[str(code)] = display
        elif isinstance(types, list):
            for idx, name in enumerate(types):
                if isinstance(name, str):
                    display = name.replace("TYPE_", "").replace("TXT_", "").replace("_", " ").title()
                    type_names[str(idx)] = display

        # Create a select entity per pin per connector
        for connector, pins in data.items():
            if not isinstance(pins, dict):
                continue
            # Get the hw type letter mapping for this connector
            connector_hw = hw_types.get(connector, {})
            # Build value→code and code→value mappings
            code_to_letter = {}
            if isinstance(connector_hw, dict):
                code_to_letter = connector_hw
            elif isinstance(connector_hw, list):
                code_to_letter = {
                    str(i): v for i, v in enumerate(connector_hw)
                }

            for pin_num, pin_data in pins.items():
                if not isinstance(pin_data, (dict, int)):
                    continue
                current_value = (
                    pin_data.get("value")
                    if isinstance(pin_data, dict)
                    else pin_data
                )

                # Build options: code → display name
                options = []
                option_map = {}  # display_name → type_code (str)
                for code, display in type_names.items():
                    options.append(display)
                    option_map[display] = code

                if not options:
                    continue

                # Current selection
                current_display = type_names.get(
                    str(current_value), f"Unknown ({current_value})"
                )

                entities.append(
                    LarnitechPinSelect(
                        admin_coord=admin_coord,
                        entry_id=entry_id,
                        module_id=module_id,
                        model=model,
                        connector=connector,
                        pin_num=pin_num,
                        options=sorted(options),
                        option_map=option_map,
                        code_to_letter=code_to_letter,
                        current_display=current_display,
                        current_code=str(current_value),
                    )
                )

    async_add_entities(entities)


class LarnitechPinSelect(SelectEntity):
    """Select entity for configuring a module pin type."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:chip"

    def __init__(
        self,
        admin_coord: LarnitechAdminCoordinator,
        entry_id: str,
        module_id: str,
        model: str,
        connector: str,
        pin_num: str,
        options: list[str],
        option_map: dict[str, str],
        code_to_letter: dict[str, str],
        current_display: str,
        current_code: str,
    ) -> None:
        """Initialize the pin select."""
        self._admin_coord = admin_coord
        self._module_id = module_id
        self._connector = connector
        self._pin_num = pin_num
        self._option_map = option_map
        self._code_to_letter = code_to_letter
        self._current_code = current_code

        self._attr_options = options
        self._attr_current_option = current_display
        self._attr_name = (
            f"{connector} Pin {pin_num} ({module_id})"
        )
        self._attr_unique_id = (
            f"{entry_id}_{module_id}_pin_{connector}_{pin_num}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

    async def async_select_option(self, option: str) -> None:
        """Set the pin type."""
        code = self._option_map.get(option)
        if code is None:
            return
        letter = self._code_to_letter.get(code, "")
        if not letter:
            return

        # Build the hw config string for this single pin change
        hw_config = f"hw[{self._connector}][{self._pin_num}]={letter}"
        try:
            await self._admin_coord.set_hw_config(
                self._module_id, hw_config
            )
            self._attr_current_option = option
            self._current_code = code
            self.async_write_ha_state()
            LOGGER.info(
                "Set module %s %s pin %s to %s (%s)",
                self._module_id,
                self._connector,
                self._pin_num,
                option,
                letter,
            )
        except Exception:
            LOGGER.exception(
                "Failed to set pin %s/%s on module %s",
                self._connector,
                self._pin_num,
                self._module_id,
            )
