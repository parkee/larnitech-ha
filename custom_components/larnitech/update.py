"""Update platform for Larnitech module firmware."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LarnitechConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech firmware update entities."""
    coordinator = entry.runtime_data
    entry_id = entry.entry_id
    entities: list[UpdateEntity] = []

    for module_id, info in coordinator.module_info.items():
        model = info.get("model", "")
        firmware = info.get("firmware", "")
        if not firmware:
            continue
        entities.append(
            LarnitechFirmwareUpdate(
                entry_id=entry_id,
                module_id=module_id,
                model=model,
                firmware=firmware,
            )
        )

    async_add_entities(entities)


def _extract_fw_date(fw_string: str) -> str:
    """Extract date from firmware string like '2021-04-19 Release v.2'."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", fw_string)
    return match.group(1) if match else fw_string


def _extract_fw_channel(fw_string: str) -> str:
    """Extract channel from firmware string."""
    if "Alpha" in fw_string:
        return "Alpha"
    if "Release" in fw_string:
        return "Release"
    return "Unknown"


class LarnitechFirmwareUpdate(UpdateEntity):
    """Firmware update entity for a Larnitech module.

    Shows current firmware version. The actual update must be performed
    through the Larnitech admin panel (no OTA API discovered yet).
    """

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_supported_features = UpdateEntityFeature(0)

    def __init__(
        self,
        entry_id: str,
        module_id: str,
        model: str,
        firmware: str,
    ) -> None:
        """Initialize the firmware update entity."""
        self._attr_unique_id = f"{entry_id}_{module_id}_firmware"
        self._fw_string = firmware
        self._attr_installed_version = _extract_fw_date(firmware)
        self._attr_title = f"{model} ({module_id})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{module_id}")},
        )

        self._attr_extra_state_attributes = {
            "channel": _extract_fw_channel(firmware),
            "full_version": firmware,
        }

    @property
    def latest_version(self) -> str | None:
        """Return the latest available version.

        We don't have an OTA update API, so latest = installed.
        If a newer version exists, the Larnitech admin panel shows it.
        """
        return self._attr_installed_version
