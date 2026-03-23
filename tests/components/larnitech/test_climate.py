"""Test the Larnitech climate platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.climate import HVACMode

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

from custom_components.larnitech.climate import LarnitechAC, LarnitechValveHeating
from custom_components.larnitech.coordinator import LarnitechCoordinator


def _make_coordinator(addr: str, status: LarnitechDeviceStatus) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.data = {addr: status}
    coordinator.get_status.return_value = status
    return coordinator


class TestLarnitechAC:
    """Test LarnitechAC entity."""

    def test_hvac_mode_off(self) -> None:
        """Test AC reports OFF when power bit is 0."""
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="38001C620331")
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.hvac_mode == HVACMode.OFF

    def test_hvac_mode_heat(self) -> None:
        """Test AC reports HEAT when mode=3 and power on."""
        # Verified: 0=Fan, 1=Cool, 2=Dry, 3=Heat, 4=Auto
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="39001C620431100000")
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_cool(self) -> None:
        """Test AC reports COOL when mode=1."""
        # byte0=0x19: power=1, mode=1=Cool
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="19001C620031")
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.hvac_mode == HVACMode.COOL

    def test_target_temperature(self) -> None:
        """Test AC temperature reading (byte 2 = 0x1C = 28)."""
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="39001C620431100000")
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.target_temperature == 28.0

    def test_fan_mode(self) -> None:
        """Test fan mode reading (byte 4 lower nibble = 4 = turbo)."""
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="39001C620431100000")
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.fan_mode == "turbo"

    def test_min_max_temp(self) -> None:
        """Test temperature range from device attributes."""
        device = LarnitechDevice(addr="407:1", type="AC", name="AC",
                                  extra={"t-min": "16", "t-delta": "16"})
        status = LarnitechDeviceStatus(addr="407:1", type="AC", state="39001C620431")
        coordinator = _make_coordinator("407:1", status)
        entity = LarnitechAC(coordinator, device)
        assert entity.min_temp == 16
        assert entity.max_temp == 32


class TestLarnitechValveHeating:
    """Test LarnitechValveHeating entity."""

    def test_hvac_mode_heat(self) -> None:
        """Test valve-heating reports HEAT when on."""
        status = LarnitechDeviceStatus(
            addr="276:6", type="valve-heating", state="on",
            extra={"meas_temp": "22.5", "setpoint_temp": "24.0"}
        )
        device = LarnitechDevice(addr="276:6", type="valve-heating", name="Rad")
        coordinator = _make_coordinator("276:6", status)
        entity = LarnitechValveHeating(coordinator, device)
        assert entity.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_off(self) -> None:
        """Test valve-heating reports OFF when off."""
        status = LarnitechDeviceStatus(
            addr="276:6", type="valve-heating", state="off"
        )
        device = LarnitechDevice(addr="276:6", type="valve-heating", name="Rad")
        coordinator = _make_coordinator("276:6", status)
        entity = LarnitechValveHeating(coordinator, device)
        assert entity.hvac_mode == HVACMode.OFF

    def test_current_temperature(self) -> None:
        """Test reading measured temperature."""
        status = LarnitechDeviceStatus(
            addr="276:6", type="valve-heating", state="on",
            extra={"meas_temp": "22.5", "setpoint_temp": "24.0"}
        )
        device = LarnitechDevice(addr="276:6", type="valve-heating", name="Rad")
        coordinator = _make_coordinator("276:6", status)
        entity = LarnitechValveHeating(coordinator, device)
        assert entity.current_temperature == 22.5

    def test_target_temperature(self) -> None:
        """Test reading setpoint temperature (read-only)."""
        status = LarnitechDeviceStatus(
            addr="276:6", type="valve-heating", state="on",
            extra={"meas_temp": "22.5", "setpoint_temp": "24.0"}
        )
        device = LarnitechDevice(addr="276:6", type="valve-heating", name="Rad")
        coordinator = _make_coordinator("276:6", status)
        entity = LarnitechValveHeating(coordinator, device)
        assert entity.target_temperature == 24.0
