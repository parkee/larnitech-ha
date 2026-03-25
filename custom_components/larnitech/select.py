"""Select platform for Larnitech module pin configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

                # Build options: code → display name
                options = []
                option_map = {}  # display_name → type_code (str)
                for code, display in type_names.items():
                    options.append(display)
                    option_map[display] = code

                if not options:
                    continue

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
                        type_names=type_names,
                    )
                )

    async_add_entities(entities)


class LarnitechPinSelect(
    CoordinatorEntity[LarnitechAdminCoordinator], SelectEntity
):
    """Select entity for configuring a module pin type.

    Reads the current pin value from the admin coordinator's polled
    HW config data, so external changes (e.g., via Larnitech UI) are
    reflected within 5 minutes.
    """

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
        type_names: dict[str, str],
    ) -> None:
        """Initialize the pin select."""
        super().__init__(admin_coord)
        self._module_id = module_id
        self._connector = connector
        self._pin_num = pin_num
        self._option_map = option_map
        self._code_to_letter = code_to_letter
        self._type_names = type_names

        self._attr_options = options
        self._attr_name = (
            f"{connector} Pin {pin_num} ({module_id})"
        )
        self._attr_unique_id = (
            f"{entry_id}_{module_id}_pin_{connector}_{pin_num}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current pin type from polled HW config data."""
        if self.coordinator.data:
            module_data = self.coordinator.data.get(self._module_id, {})
            hw_config = module_data.get("hw_config")
            if isinstance(hw_config, dict):
                data = hw_config.get("data", {})
                conn_pins = data.get(self._connector, {})
                pin_data = conn_pins.get(self._pin_num)
                if pin_data is not None:
                    current_code = (
                        pin_data.get("value")
                        if isinstance(pin_data, dict)
                        else pin_data
                    )
                    return self._type_names.get(
                        str(current_code),
                        f"Unknown ({current_code})",
                    )
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the pin type.

        Uses set_pin_type which fetches the current HW config and sends
        ALL pins for all connectors to avoid resetting other pins.
        """
        code = self._option_map.get(option)
        if code is None:
            return
        letter = self._code_to_letter.get(code, "")
        if not letter:
            return

        try:
            result = await self.coordinator.set_pin_type(
                self._module_id,
                self._connector,
                self._pin_num,
                letter,
            )
        except Exception:
            LOGGER.exception(
                "Failed to set pin %s/%s on module %s",
                self._connector,
                self._pin_num,
                self._module_id,
            )
            raise HomeAssistantError(
                f"Failed to set pin {self._connector}/{self._pin_num}"
            ) from None

        success = result.get("success", False) if isinstance(result, dict) else bool(result)
        message = result.get("message", "") if isinstance(result, dict) else ""
        if not success:
            raise HomeAssistantError(
                f"Pin config change rejected: {message}"
            )
