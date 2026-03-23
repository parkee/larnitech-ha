"""Config flow for the Larnitech integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from pylarnitech import (
    LarnitechAuthError,
    LarnitechClient,
    LarnitechConnectionError,
    LarnitechTimeoutError,
)
from pylarnitech.admin import LarnitechAdminClient

from .const import (
    CONF_API_KEY,
    CONF_HTTP_PORT,
    CONF_WS_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_WS_PORT, default=DEFAULT_WS_PORT): int,
        vol.Optional(CONF_HTTP_PORT, default=DEFAULT_HTTP_PORT): int,
    }
)


class LarnitechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Larnitech."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            api_key = user_input[CONF_API_KEY]
            ws_port = user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT)
            http_port = user_input.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)

            # Try to connect and validate
            client = LarnitechClient(
                host=host,
                api_key=api_key,
                ws_port=ws_port,
                http_port=http_port,
            )

            try:
                device_count = await client.validate_connection()
            except LarnitechAuthError:
                errors["base"] = "invalid_auth"
            except (LarnitechConnectionError, LarnitechTimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                if device_count == 0:
                    errors[CONF_API_KEY] = "invalid_auth"
                else:
                    # Try to get serial from admin panel for unique_id
                    unique_id = await self._get_serial(host)
                    if unique_id:
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured(
                            updates={CONF_HOST: host}
                        )

                    return self.async_create_entry(
                        title=f"Larnitech ({host})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _get_serial(self, host: str) -> str | None:
        """Try to get the controller serial from the admin panel."""
        admin = LarnitechAdminClient(host=host)
        try:
            await admin.login()
            info = await admin.get_controller_info()
            return info.serial or None
        except Exception:
            LOGGER.debug(
                "Could not get serial from admin panel",
                exc_info=True,
            )
            return None
        finally:
            await admin.close()
