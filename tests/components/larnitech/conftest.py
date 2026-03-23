"""Common fixtures for the Larnitech tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pylarnitech.models import LarnitechDevice, LarnitechDeviceStatus

MOCK_HOST = "192.168.4.100"
MOCK_API_KEY = "testkey123"
MOCK_SERIAL = "test_serial"

MOCK_CONFIG_DATA = {
    "host": MOCK_HOST,
    "api_key": MOCK_API_KEY,
    "ws_port": 8080,
    "http_port": 8888,
}

MOCK_DEVICES = [
    LarnitechDevice(addr="388:3", type="lamp", name="Kitchen Light", n_addr=99331),
    LarnitechDevice(addr="298:3", type="dimmer-lamp", name="Dimmer", n_addr=76291),
    LarnitechDevice(addr="407:1", type="AC", name="Office AC", n_addr=104193,
                    extra={"t-min": "16", "t-delta": "16"}),
    LarnitechDevice(addr="276:6", type="valve-heating", name="Radiator",
                    n_addr=70662, extra={"modes": [{"mode_named": "Comfort"}]}),
    LarnitechDevice(addr="426:5", type="blinds", name="Blinds", n_addr=109061),
    LarnitechDevice(addr="999:3", type="temperature-sensor", name="Temp", n_addr=255747),
    LarnitechDevice(addr="509:30", type="motion-sensor", name="Motion", n_addr=130334),
    LarnitechDevice(addr="279:15", type="door-sensor", name="Door", n_addr=71439),
    LarnitechDevice(addr="279:14", type="leak-sensor", name="Leak", n_addr=71438),
    LarnitechDevice(addr="279:1", type="valve", name="Water Valve", n_addr=71425),
    LarnitechDevice(addr="339:250", type="script", name="Test Script", n_addr=87034),
    LarnitechDevice(addr="451:250", type="light-scheme", name="All Lights", n_addr=115706),
    LarnitechDevice(addr="2048:248", type="remote-control", name="IR Remote",
                    n_addr=524536, extra={"sygnals": [
                        {"transmitter-addr": "288:11", "value": "AABB", "name": "Power"},
                    ]}),
    LarnitechDevice(addr="999:4", type="virtual", name="Pressure", n_addr=255748),
    LarnitechDevice(addr="188:250", type="climate-control", name="Office Climate",
                    n_addr=48378),
    LarnitechDevice(addr="288:11", type="ir-transmitter", name="IR transmitter",
                    n_addr=73739),
]

MOCK_STATUSES = {
    "388:3": LarnitechDeviceStatus(addr="388:3", type="lamp", state="off"),
    "298:3": LarnitechDeviceStatus(addr="298:3", type="dimmer-lamp", state="off",
                                    extra={"brightness": 50}),
    "407:1": LarnitechDeviceStatus(addr="407:1", type="AC", state="39001C620431100000"),
    "276:6": LarnitechDeviceStatus(addr="276:6", type="valve-heating", state="on",
                                    extra={"meas_temp": "22.5", "setpoint_temp": "24.0",
                                           "mode": "manual"}),
    "426:5": LarnitechDeviceStatus(addr="426:5", type="blinds", state="00FAFA"),
    "999:3": LarnitechDeviceStatus(addr="999:3", type="temperature-sensor", state="22.5"),
    "509:30": LarnitechDeviceStatus(addr="509:30", type="motion-sensor", state="0.0"),
    "279:15": LarnitechDeviceStatus(addr="279:15", type="door-sensor", state="closed"),
    "279:14": LarnitechDeviceStatus(addr="279:14", type="leak-sensor", state="no leakage"),
    "279:1": LarnitechDeviceStatus(addr="279:1", type="valve", state="open"),
    "339:250": LarnitechDeviceStatus(addr="339:250", type="script", state="undefined"),
    "451:250": LarnitechDeviceStatus(addr="451:250", type="light-scheme", state="off"),
    "2048:248": LarnitechDeviceStatus(addr="2048:248", type="remote-control",
                                       state="undefined"),
    "999:4": LarnitechDeviceStatus(addr="999:4", type="virtual",
                                    state="3736356D6D4867"),
    "188:250": LarnitechDeviceStatus(
        addr="188:250", type="climate-control",
        state="000581818181008100810081008100810081311B008100810081",
    ),
    "288:11": LarnitechDeviceStatus(
        addr="288:11", type="ir-transmitter", state="undefined",
    ),
}


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Create a mock LarnitechClient."""
    with patch(
        "custom_components.larnitech.LarnitechClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.host = MOCK_HOST
        client.connected = True
        client.validate_connection = AsyncMock(return_value=len(MOCK_DEVICES))
        client.get_devices = AsyncMock(return_value=MOCK_DEVICES)
        client.get_all_statuses = AsyncMock(
            return_value=list(MOCK_STATUSES.values())
        )
        client.get_device_status = AsyncMock(
            side_effect=lambda addr: MOCK_STATUSES.get(addr)
        )
        client.set_device_status = AsyncMock(return_value={"status": {"state": "on"}})
        client.set_device_status_raw = AsyncMock(return_value={"status": {"state": "ff"}})
        client.send_ir_signal = AsyncMock(return_value={"status": {"state": "AABB"}})
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.on_status_update = MagicMock(return_value=lambda: None)
        client.on_disconnect = MagicMock(return_value=lambda: None)
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.larnitech.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
