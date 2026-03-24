"""Constants for the Larnitech integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "larnitech"
LOGGER = logging.getLogger(__package__)

CONF_API_KEY: Final = "api_key"
CONF_WS_PORT: Final = "ws_port"
CONF_HTTP_PORT: Final = "http_port"

DEFAULT_WS_PORT: Final = 8080
DEFAULT_HTTP_PORT: Final = 8888

PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
    Platform.VALVE,
]

# TODO: Larnitech device types not yet mapped to HA platforms:
#
# "switch" (74 devices) — Physical KNX wall button panels (4-button + multitouch).
#   These are KNX switches via KNX bridge. The KNX integration may handle them
#   natively. Worth checking if WebSocket push delivers button press events;
#   if so, map to Platform.EVENT with EventDeviceClass.BUTTON.
#   Status is always "undefined" via HTTP API — input-only, no controllable state.
#
# "com-port" (5 devices) — RS232 serial port modules.
#   4 of these are DALI bus gateways (have "dali": "yes" attribute) bridging
#   CAN bus to DALI lighting bus. DALI lights already appear as lamp/dimmer
#   entities. The 5th (DE-MG.plus RS232 at 188:40) has raw hex data in its
#   status that could be a meter or sensor protocol.
#   Worth investigating the 188:40 data format and exposing as a sensor if
#   the protocol can be identified.
#
# "ir-receiver" (1 device) — Passive IR receiver on DE-MG.plus controller.
#   Used for IR learning. Status always "undefined" via HTTP API.
#   Could expose raw received signals if native protocol (port 55555) pushes
#   them, but HTTP API shows no data.
#
# "json" (1 device) — Internal API endpoint device. No user-facing purpose.
