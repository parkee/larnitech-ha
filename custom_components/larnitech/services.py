"""Service actions for the Larnitech integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from pylarnitech.admin import LarnitechAdminClient

from .const import DOMAIN, LOGGER

SERVICE_SET_MODULE_HW = "set_module_hw"
SERVICE_GET_MODULE_HW_CONFIG = "get_module_hw_config"
SERVICE_GET_MODULE_LOGS = "get_module_logs"

SET_MODULE_HW_SCHEMA = vol.Schema(
    {
        vol.Required("module_id"): str,
        vol.Required("hw_config"): str,
    }
)

GET_MODULE_HW_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("module_id"): str,
    }
)

GET_MODULE_LOGS_SCHEMA = vol.Schema(
    {
        vol.Required("module_id"): str,
    }
)


def _get_host(hass: HomeAssistant) -> str:
    """Get the controller host from the first config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ValueError("No Larnitech integration configured")
    return entries[0].data[CONF_HOST]


async def _get_admin(hass: HomeAssistant) -> LarnitechAdminClient:
    """Create and authenticate an admin client."""
    host = _get_host(hass)
    admin = LarnitechAdminClient(host=host)
    await admin.login()
    return admin


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Larnitech service actions."""

    async def handle_set_module_hw(call: ServiceCall) -> None:
        """Handle set_module_hw service call.

        hw_config should contain ALL pins for the connector, e.g.:
        hw[IN][1]=K&hw[IN][2]=G&hw[IN][3]=K&...
        Sending a single pin will reset all other pins to defaults.
        """
        module_id = call.data["module_id"]
        hw_config = call.data["hw_config"]
        admin = await _get_admin(hass)
        try:
            result = await admin.set_module_hw(module_id, hw_config)
            success = result.get("success", False) if isinstance(result, dict) else bool(result)
            message = result.get("message", "") if isinstance(result, dict) else ""
            if success:
                LOGGER.info("Set HW config for module %s: success", module_id)
            else:
                LOGGER.warning(
                    "Set HW config for module %s rejected: %s",
                    module_id,
                    message,
                )
        finally:
            await admin.close()

    async def handle_get_module_hw_config(
        call: ServiceCall,
    ) -> dict[str, Any]:
        """Handle get_module_hw_config service call."""
        module_id = call.data["module_id"]
        admin = await _get_admin(hass)
        try:
            return await admin.get_module_hw_config(module_id)
        finally:
            await admin.close()

    async def handle_get_module_logs(
        call: ServiceCall,
    ) -> dict[str, Any]:
        """Handle get_module_logs service call."""
        module_id = call.data["module_id"]
        admin = await _get_admin(hass)
        try:
            logs = await admin.get_module_logs(module_id)
            return {"module_id": module_id, "logs": logs}
        finally:
            await admin.close()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MODULE_HW,
        handle_set_module_hw,
        schema=SET_MODULE_HW_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MODULE_HW_CONFIG,
        handle_get_module_hw_config,
        schema=GET_MODULE_HW_CONFIG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MODULE_LOGS,
        handle_get_module_logs,
        schema=GET_MODULE_LOGS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
