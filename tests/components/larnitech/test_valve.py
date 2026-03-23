"""Test the Larnitech valve platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.valve import ValveDeviceClass

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

from custom_components.larnitech.coordinator import LarnitechCoordinator
from custom_components.larnitech.valve import LarnitechValve


def _make_valve(state: str) -> LarnitechValve:
    """Create a LarnitechValve with mocked coordinator."""
    device = LarnitechDevice(addr="279:1", type="valve", name="Water Valve")
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    status = LarnitechDeviceStatus(addr="279:1", type="valve", state=state)
    coordinator.data = {"279:1": status}
    coordinator.get_status.return_value = status
    return LarnitechValve(coordinator, device)


class TestLarnitechValve:
    """Test LarnitechValve entity."""

    def test_open_valve(self) -> None:
        """Test valve reports open."""
        entity = _make_valve("open")
        assert entity.is_closed is False

    def test_closed_valve(self) -> None:
        """Test valve reports closed."""
        entity = _make_valve("closed")
        assert entity.is_closed is True

    def test_device_class(self) -> None:
        """Test valve has WATER device class."""
        entity = _make_valve("open")
        assert entity.device_class == ValveDeviceClass.WATER

    def test_reports_position_false(self) -> None:
        """Test valve does not report position."""
        entity = _make_valve("open")
        assert entity.reports_position is False
