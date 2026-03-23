"""Test the Larnitech sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

from custom_components.larnitech.coordinator import LarnitechCoordinator
from custom_components.larnitech.sensor import (
    LarnitechClimateControlSensor,
    LarnitechSensor,
    LarnitechVirtualSensor,
    SENSOR_DESCRIPTIONS,
)


def _make_coordinator(addr: str, status: LarnitechDeviceStatus) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.data = {addr: status}
    coordinator.get_status.return_value = status
    return coordinator


class TestLarnitechSensor:
    """Test numeric sensors."""

    def test_temperature_sensor(self) -> None:
        """Test temperature sensor reads float."""
        status = LarnitechDeviceStatus(addr="999:3", type="temperature-sensor", state="22.5")
        device = LarnitechDevice(addr="999:3", type="temperature-sensor", name="Temp")
        coordinator = _make_coordinator("999:3", status)
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "temperature"][0]
        entity = LarnitechSensor(coordinator, device, desc)
        assert entity.native_value == 22.5

    def test_undefined_state(self) -> None:
        """Test sensor with undefined state returns None."""
        status = LarnitechDeviceStatus(addr="999:3", type="temperature-sensor", state="undefined")
        device = LarnitechDevice(addr="999:3", type="temperature-sensor", name="Temp")
        coordinator = _make_coordinator("999:3", status)
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "temperature"][0]
        entity = LarnitechSensor(coordinator, device, desc)
        assert entity.native_value is None

    def test_non_numeric_state(self) -> None:
        """Test sensor gracefully handles non-numeric state."""
        status = LarnitechDeviceStatus(addr="999:3", type="temperature-sensor", state="error")
        device = LarnitechDevice(addr="999:3", type="temperature-sensor", name="Temp")
        coordinator = _make_coordinator("999:3", status)
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "temperature"][0]
        entity = LarnitechSensor(coordinator, device, desc)
        assert entity.native_value is None


class TestLarnitechVirtualSensor:
    """Test virtual (text) sensors."""

    def test_decode_hex_text(self) -> None:
        """Test hex-encoded text decoding."""
        # "765mmHg" in hex
        status = LarnitechDeviceStatus(addr="999:4", type="virtual", state="3736356D6D4867")
        device = LarnitechDevice(addr="999:4", type="virtual", name="Pressure")
        coordinator = _make_coordinator("999:4", status)
        entity = LarnitechVirtualSensor(coordinator, device)
        assert entity.native_value == "765mmHg"

    def test_decode_weather(self) -> None:
        """Test decoding weather description."""
        # "few clouds" in hex
        status = LarnitechDeviceStatus(addr="999:5", type="virtual", state="66657720636C6F756473")
        device = LarnitechDevice(addr="999:5", type="virtual", name="Outside")
        coordinator = _make_coordinator("999:5", status)
        entity = LarnitechVirtualSensor(coordinator, device)
        assert entity.native_value == "few clouds"

    def test_undefined(self) -> None:
        """Test undefined state."""
        status = LarnitechDeviceStatus(addr="999:4", type="virtual", state="undefined")
        device = LarnitechDevice(addr="999:4", type="virtual", name="Pressure")
        coordinator = _make_coordinator("999:4", status)
        entity = LarnitechVirtualSensor(coordinator, device)
        assert entity.native_value is None


class TestLarnitechClimateControlSensor:
    """Test climate-control temperature sensor."""

    def test_decode_temperature(self) -> None:
        """Test temperature extraction from hex state (bytes 18-19)."""
        # Bytes 18-19: 0x31, 0x1B → statusFloat2 = 27.19°C
        state = "000581818181008100810081008100810081311B008100810081"
        status = LarnitechDeviceStatus(addr="188:250", type="climate-control", state=state)
        device = LarnitechDevice(addr="188:250", type="climate-control", name="Office")
        coordinator = _make_coordinator("188:250", status)
        entity = LarnitechClimateControlSensor(coordinator, device)
        value = entity.native_value
        assert value is not None
        assert abs(value - 27.19) < 0.1

    def test_short_state(self) -> None:
        """Test handling of state too short for temperature."""
        status = LarnitechDeviceStatus(addr="188:250", type="climate-control", state="0005")
        device = LarnitechDevice(addr="188:250", type="climate-control", name="Office")
        coordinator = _make_coordinator("188:250", status)
        entity = LarnitechClimateControlSensor(coordinator, device)
        assert entity.native_value is None
