"""Config flow for the Larnitech integration.

Two transports are offered: ``native`` (TCP 55555 — writes earn the controller's
automation backoff, recommended) and ``http`` (HTTP 8888 + WebSocket 8080, the original
behaviour). An existing entry can be reconfigured to switch transport in place — the
entry (and therefore all its entities) is kept, only ``entry.data`` changes.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from pylarnitech import (
    LarnitechAuthError,
    LarnitechClient,
    LarnitechConnectionError,
    LarnitechNativeClient,
    LarnitechTimeoutError,
)
from pylarnitech.admin import LarnitechAdminClient

from .const import (
    CONF_ACCESS_KEY,
    CONF_API_KEY,
    CONF_CONNECTION_MODE,
    CONF_HTTP_PORT,
    CONF_NATIVE_PORT,
    CONF_WS_PORT,
    CONNECTION_MODE_HTTP,
    CONNECTION_MODE_NATIVE,
    DEFAULT_HTTP_PORT,
    DEFAULT_NATIVE_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
    LOGGER,
)


class LarnitechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Larnitech."""

    VERSION = 1

    # ---- entry points ----

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step when adding: choose the transport."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CONNECTION_MODE_NATIVE, CONNECTION_MODE_HTTP],
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step when reconfiguring an existing entry: choose the transport."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[CONNECTION_MODE_NATIVE, CONNECTION_MODE_HTTP],
        )

    # ---- per-transport forms (shared by add + reconfigure) ----

    async def async_step_native(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect/validate native (TCP 55555) settings."""
        errors: dict[str, str] = {}
        existing = self._existing_data()

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            access_key = (user_input.get(CONF_ACCESS_KEY) or "").strip()
            native_port = user_input.get(CONF_NATIVE_PORT, DEFAULT_NATIVE_PORT)

            if not access_key:
                access_key = await self._fetch_access_key(host)
            if not access_key:
                errors[CONF_ACCESS_KEY] = "access_key_required"
            else:
                data = {
                    CONF_HOST: host,
                    CONF_CONNECTION_MODE: CONNECTION_MODE_NATIVE,
                    CONF_ACCESS_KEY: access_key,
                    CONF_NATIVE_PORT: native_port,
                }
                result = await self._validate_and_finish(
                    host,
                    data,
                    LarnitechNativeClient(host, access_key, port=native_port),
                )
                if isinstance(result, str):
                    errors["base"] = result
                else:
                    return result

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=existing.get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_ACCESS_KEY, default=existing.get(CONF_ACCESS_KEY, "")
                ): str,
                vol.Optional(
                    CONF_NATIVE_PORT,
                    default=existing.get(CONF_NATIVE_PORT, DEFAULT_NATIVE_PORT),
                ): int,
            }
        )
        return self.async_show_form(
            step_id=CONNECTION_MODE_NATIVE, data_schema=schema, errors=errors
        )

    async def async_step_http(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect/validate HTTP (8888 + WebSocket 8080) settings."""
        errors: dict[str, str] = {}
        existing = self._existing_data()

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            data = {
                CONF_HOST: host,
                CONF_CONNECTION_MODE: CONNECTION_MODE_HTTP,
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_WS_PORT: user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT),
                CONF_HTTP_PORT: user_input.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT),
            }
            client = LarnitechClient(
                host=host,
                api_key=data[CONF_API_KEY],
                ws_port=data[CONF_WS_PORT],
                http_port=data[CONF_HTTP_PORT],
            )
            result = await self._validate_and_finish(host, data, client)
            if isinstance(result, str):
                errors["base"] = result
            else:
                return result

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=existing.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_API_KEY, default=existing.get(CONF_API_KEY, "")
                ): str,
                vol.Optional(
                    CONF_WS_PORT, default=existing.get(CONF_WS_PORT, DEFAULT_WS_PORT)
                ): int,
                vol.Optional(
                    CONF_HTTP_PORT,
                    default=existing.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT),
                ): int,
            }
        )
        return self.async_show_form(
            step_id=CONNECTION_MODE_HTTP, data_schema=schema, errors=errors
        )

    # ---- helpers ----

    def _existing_data(self) -> dict[str, Any]:
        """Current entry data when reconfiguring (to prefill the form), else empty."""
        if self.source == SOURCE_RECONFIGURE:
            return dict(self._get_reconfigure_entry().data)
        return {}

    async def _validate_and_finish(
        self,
        host: str,
        data: dict[str, Any],
        client: LarnitechClient | LarnitechNativeClient,
    ) -> ConfigFlowResult | str:
        """Validate the connection then create or update the entry.

        Returns a ConfigFlowResult on success, or an error key string on failure.
        """
        try:
            device_count = await client.validate_connection()
        except LarnitechAuthError:
            return "invalid_auth"
        except (LarnitechConnectionError, LarnitechTimeoutError):
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception during config flow")
            return "unknown"
        finally:
            if isinstance(client, LarnitechNativeClient):
                await client.disconnect()

        if device_count == 0:
            return "invalid_auth"

        unique_id = await self._get_serial(host)

        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            if unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_controller")
            return self.async_update_reload_and_abort(entry, data=data)

        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(title=f"Larnitech ({host})", data=data)

    async def _fetch_access_key(self, host: str) -> str:
        """Try to fetch the native Access key from the admin panel (admin/admin)."""
        admin = LarnitechAdminClient(host=host)
        try:
            await admin.login()
            ws = await admin.get_ws_data()
            return str(ws.get("key") or "")
        except Exception:  # noqa: BLE001
            LOGGER.debug("Could not auto-fetch native access key", exc_info=True)
            return ""
        finally:
            await admin.close()

    async def _get_serial(self, host: str) -> str | None:
        """Try to get the controller serial from the admin panel for the unique_id."""
        admin = LarnitechAdminClient(host=host)
        try:
            await admin.login()
            info = await admin.get_controller_info()
            return info.serial or None
        except Exception:
            LOGGER.debug("Could not get serial from admin panel", exc_info=True)
            return None
        finally:
            await admin.close()
