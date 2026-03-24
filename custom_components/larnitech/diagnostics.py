"""Diagnostics support for the Larnitech integration."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from pylarnitech.admin import LarnitechAdminClient

from .const import CONF_API_KEY, LOGGER
from .coordinator import LarnitechConfigEntry

TO_REDACT = {CONF_API_KEY, "api_key", "key", "password", "secretKey", "serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    device_types = Counter(
        d.type for d in coordinator.devices.values()
    )

    # Fetch live module health from admin API
    module_health: dict[str, Any] = {}
    try:
        admin = LarnitechAdminClient(host=entry.data[CONF_HOST])
        await admin.login()
        modules_data = await admin.get_modules()
        for mid, info in modules_data.items():
            module_health[mid] = {
                "model": info.get("model"),
                "firmware": info.get("firmware"),
                "primary_area": info.get("primary_area"),
            }
        await admin.close()
    except Exception:
        LOGGER.debug("Could not fetch module health for diagnostics")

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_count": len(coordinator.devices),
        "device_types": dict(device_types),
        "module_count": len(coordinator.module_info),
        "module_info": module_health or {
            mid: {
                "model": info.get("model"),
                "firmware": info.get("firmware"),
                "primary_area": info.get("primary_area"),
            }
            for mid, info in coordinator.module_info.items()
        },
        "websocket_connected": coordinator.client.connected,
        "coordinator_last_update_success": coordinator.last_update_success,
    }
