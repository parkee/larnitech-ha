"""Sensor platform for the Larnitech integration."""

from __future__ import annotations

from dataclasses import dataclass

from pylarnitech.const import (
    DEVICE_TYPE_CLIMATE_CONTROL,
    DEVICE_TYPE_CURRENT_SENSOR,
    DEVICE_TYPE_HUMIDITY_SENSOR,
    DEVICE_TYPE_ILLUMINATION_SENSOR,
    DEVICE_TYPE_TEMPERATURE_SENSOR,
    DEVICE_TYPE_VIRTUAL,
    DEVICE_TYPE_VOLTAGE_SENSOR,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry, LarnitechCoordinator
from .entity import LarnitechEntity


@dataclass(frozen=True, kw_only=True)
class LarnitechSensorDescription(SensorEntityDescription):
    """Describe a Larnitech sensor."""

    device_type: str


SENSOR_DESCRIPTIONS: tuple[LarnitechSensorDescription, ...] = (
    LarnitechSensorDescription(
        key="temperature",
        device_type=DEVICE_TYPE_TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    LarnitechSensorDescription(
        key="humidity",
        device_type=DEVICE_TYPE_HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    LarnitechSensorDescription(
        key="illuminance",
        device_type=DEVICE_TYPE_ILLUMINATION_SENSOR,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    LarnitechSensorDescription(
        key="current",
        device_type=DEVICE_TYPE_CURRENT_SENSOR,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    LarnitechSensorDescription(
        key="voltage",
        device_type=DEVICE_TYPE_VOLTAGE_SENSOR,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
)

_TYPE_TO_DESCRIPTION = {d.device_type: d for d in SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech sensor entities."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for device in coordinator.devices.values():
        if description := _TYPE_TO_DESCRIPTION.get(device.type):
            entities.append(
                LarnitechSensor(coordinator, device, description)
            )
        elif device.type == DEVICE_TYPE_VIRTUAL:
            entities.append(LarnitechVirtualSensor(coordinator, device))
        elif device.type == DEVICE_TYPE_CLIMATE_CONTROL:
            entities.append(
                LarnitechClimateControlSensor(coordinator, device)
            )

    async_add_entities(entities)


class LarnitechSensor(LarnitechEntity, SensorEntity):
    """Representation of a Larnitech numeric sensor."""

    entity_description: LarnitechSensorDescription
    _attr_name = None

    def __init__(
        self,
        coordinator: LarnitechCoordinator,
        device,
        description: LarnitechSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, unique_id_suffix=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        status = self.device_status
        if status is None or status.state in ("undefined", ""):
            return None
        try:
            return float(status.state)
        except (ValueError, TypeError):
            return None


class LarnitechVirtualSensor(LarnitechEntity, SensorEntity):
    """Representation of a Larnitech virtual device as a text sensor.

    Virtual devices store their state as hex-encoded UTF-8 text.
    Examples: "765mmHg", "few clouds", weather descriptions.
    """

    _attr_name = None

    @property
    def native_value(self) -> str | None:
        """Return the decoded text value."""
        status = self.device_status
        if status is None or status.state in ("undefined", ""):
            return None
        try:
            return bytes.fromhex(status.state).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return status.state


class LarnitechClimateControlSensor(LarnitechEntity, SensorEntity):
    """Representation of a Larnitech climate-control as a temperature sensor.

    Climate-control devices have a complex hex state. Bytes 18-19 contain
    the current temperature as a statusFloat2 value.
    """

    _attr_name = None
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: LarnitechCoordinator, device) -> None:
        """Initialize the climate control sensor."""
        super().__init__(coordinator, device, unique_id_suffix="temperature")

    @property
    def native_value(self) -> float | None:
        """Return the temperature from the climate-control state."""
        status = self.device_status
        if status is None or status.state in ("undefined", ""):
            return None
        try:
            b = bytes.fromhex(status.state)
        except (ValueError, TypeError):
            return None
        if len(b) < 20:
            return None
        # Bytes 18-19 are statusFloat2 temperature
        import struct

        raw = struct.unpack("<h", bytes([b[18], b[19]]))[0]
        return raw / 256.0
