"""Build the right transport client (native or HTTP) from a config entry's data."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST
from pylarnitech import LarnitechClient, LarnitechNativeClient

from .const import (
    CONF_ACCESS_KEY,
    CONF_API_KEY,
    CONF_CONNECTION_MODE,
    CONF_HTTP_PORT,
    CONF_NATIVE_PORT,
    CONF_WS_PORT,
    CONNECTION_MODE_NATIVE,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_HTTP_PORT,
    DEFAULT_NATIVE_PORT,
    DEFAULT_WS_PORT,
)

# Both clients expose the same public surface; the rest of the integration is
# transport-agnostic.
LarnitechTransport = LarnitechClient | LarnitechNativeClient


def connection_mode(data: dict[str, Any]) -> str:
    """Return the configured connection mode, defaulting to http for legacy entries."""
    return data.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)


def create_client(data: dict[str, Any]) -> LarnitechTransport:
    """Create the transport client for a config entry's data dict."""
    if connection_mode(data) == CONNECTION_MODE_NATIVE:
        return LarnitechNativeClient(
            host=data[CONF_HOST],
            access_key=data[CONF_ACCESS_KEY],
            port=data.get(CONF_NATIVE_PORT, DEFAULT_NATIVE_PORT),
        )
    return LarnitechClient(
        host=data[CONF_HOST],
        api_key=data[CONF_API_KEY],
        ws_port=data.get(CONF_WS_PORT, DEFAULT_WS_PORT),
        http_port=data.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT),
    )
