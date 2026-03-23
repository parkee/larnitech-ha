"""Test the Larnitech light platform."""

from __future__ import annotations

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

from custom_components.larnitech.coordinator import LarnitechCoordinator
from custom_components.larnitech.light import LarnitechDimmerLight, LarnitechLight


class TestLarnitechLight:
    """Test LarnitechLight entity."""

    def test_is_on_true(self) -> None:
        """Test light reports on correctly."""
        entity = _make_light("on")
        assert entity.is_on is True

    def test_is_on_false(self) -> None:
        """Test light reports off correctly."""
        entity = _make_light("off")
        assert entity.is_on is False

    def test_is_on_none_when_no_status(self) -> None:
        """Test light reports None when no status available."""
        entity = _make_light(None)
        assert entity.is_on is None


class TestLarnitechDimmerLight:
    """Test LarnitechDimmerLight entity."""

    def test_brightness_conversion(self) -> None:
        """Test Larnitech 0-100 to HA 0-255 conversion."""
        entity = _make_dimmer("on", 50)
        # 50 * 255 / 100 = 127.5 → 128
        assert entity.brightness == 128

    def test_brightness_zero(self) -> None:
        """Test zero brightness."""
        entity = _make_dimmer("off", 0)
        assert entity.brightness == 0

    def test_brightness_full(self) -> None:
        """Test full brightness."""
        entity = _make_dimmer("on", 100)
        assert entity.brightness == 255

    def test_brightness_none(self) -> None:
        """Test brightness when not available."""
        entity = _make_dimmer("off", None)
        assert entity.brightness is None


# ---- helpers ----

def _make_light(state: str | None) -> LarnitechLight:
    """Create a LarnitechLight with mocked coordinator."""
    from unittest.mock import MagicMock

    device = LarnitechDevice(addr="388:3", type="lamp", name="Test Light")
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"

    if state is not None:
        coordinator.data = {
            "388:3": LarnitechDeviceStatus(addr="388:3", type="lamp", state=state)
        }
        coordinator.get_status.return_value = coordinator.data["388:3"]
    else:
        coordinator.data = {}
        coordinator.get_status.return_value = None

    entity = LarnitechLight(coordinator, device)
    return entity


def _make_dimmer(state: str, brightness: int | None) -> LarnitechDimmerLight:
    """Create a LarnitechDimmerLight with mocked coordinator."""
    from unittest.mock import MagicMock

    device = LarnitechDevice(addr="298:3", type="dimmer-lamp", name="Test Dimmer")
    coordinator = MagicMock(spec=LarnitechCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"

    extra = {"brightness": brightness} if brightness is not None else {}
    coordinator.data = {
        "298:3": LarnitechDeviceStatus(
            addr="298:3", type="dimmer-lamp", state=state, extra=extra
        )
    }
    coordinator.get_status.return_value = coordinator.data["298:3"]

    entity = LarnitechDimmerLight(coordinator, device)
    return entity
