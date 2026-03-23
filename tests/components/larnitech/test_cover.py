"""Test the Larnitech cover platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

from custom_components.larnitech.coordinator import LarnitechCoordinator
from custom_components.larnitech.cover import LarnitechCover


def _make_cover(state: str) -> LarnitechCover:
    """Create a LarnitechCover with mocked coordinator."""
    device = LarnitechDevice(addr="426:5", type="blinds", name="Test Blinds")
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    status = LarnitechDeviceStatus(addr="426:5", type="blinds", state=state)
    coordinator.data = {"426:5": status}
    coordinator.get_status.return_value = status
    return LarnitechCover(coordinator, device)


class TestLarnitechCover:
    """Test LarnitechCover entity."""

    def test_fully_open(self) -> None:
        """Test fully open blinds."""
        entity = _make_cover("00FAFA")
        assert entity.is_closed is False
        assert entity.current_cover_position == 100
        assert entity.current_cover_tilt_position == 100

    def test_fully_closed(self) -> None:
        """Test fully closed blinds."""
        entity = _make_cover("000000")
        assert entity.is_closed is True
        assert entity.current_cover_position == 0
        assert entity.current_cover_tilt_position == 0

    def test_half_open(self) -> None:
        """Test half-open blinds."""
        entity = _make_cover("007D7D")
        assert entity.is_closed is False
        assert entity.current_cover_position == 50
        assert entity.current_cover_tilt_position == 50

    def test_moving_state(self) -> None:
        """Test blinds in motion."""
        entity = _make_cover("08FAFA")
        assert entity.is_closed is False
        assert entity.current_cover_position == 100
