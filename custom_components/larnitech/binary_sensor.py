"""Binary sensor platform for the Larnitech integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylarnitech.const import (
    DEVICE_TYPE_DOOR_SENSOR,
    DEVICE_TYPE_LEAK_SENSOR,
    DEVICE_TYPE_MOTION_SENSOR,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity



@dataclass(frozen=True, kw_only=True)
class LarnitechBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Larnitech binary sensor."""

    device_type: str
    is_on_fn: Any  # Callable[[str], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[LarnitechBinarySensorDescription, ...] = (
    LarnitechBinarySensorDescription(
        key="motion",
        device_type=DEVICE_TYPE_MOTION_SENSOR,
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda state: state == "1.0",
    ),
    LarnitechBinarySensorDescription(
        key="door",
        device_type=DEVICE_TYPE_DOOR_SENSOR,
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=lambda state: state == "opened",
    ),
    LarnitechBinarySensorDescription(
        key="leak",
        device_type=DEVICE_TYPE_LEAK_SENSOR,
        device_class=BinarySensorDeviceClass.MOISTURE,
        is_on_fn=lambda state: state != "no leakage",
    ),
)

_TYPE_TO_DESCRIPTION = {d.device_type: d for d in BINARY_SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech binary sensor entities."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []

    for device in coordinator.devices.values():
        if description := _TYPE_TO_DESCRIPTION.get(device.type):
            entities.append(
                LarnitechBinarySensor(coordinator, device, description)
            )

    async_add_entities(entities)


class LarnitechBinarySensor(LarnitechEntity, BinarySensorEntity):
    """Representation of a Larnitech binary sensor."""

    entity_description: LarnitechBinarySensorDescription

    def __init__(
        self,
        coordinator,
        device,
        description: LarnitechBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device, unique_id_suffix=description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        status = self.device_status
        if status is None or status.state in ("undefined", ""):
            return None
        return self.entity_description.is_on_fn(status.state)
