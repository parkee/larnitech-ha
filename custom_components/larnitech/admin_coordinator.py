"""Admin API coordinator for module health and configuration data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pylarnitech.admin import LarnitechAdminClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

# Poll module health + HW config every 5 minutes
_ADMIN_POLL_INTERVAL = timedelta(minutes=5)


class LarnitechAdminCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for Larnitech admin panel data.

    Manages a single persistent admin session. Re-authenticates only
    when a request fails with an auth error.

    Polls module health (temp, uptime, status) and HW configs every
    5 minutes so that select/number entities reflect external changes.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize the admin coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="larnitech_admin",
            update_interval=_ADMIN_POLL_INTERVAL,
        )
        self._host = host
        self._admin: LarnitechAdminClient | None = None
        self._logged_in = False
        # Module IDs that have HW configs (populated by fetch_all_hw_configs)
        self._hw_module_ids: set[str] = set()

    async def _ensure_admin(self) -> LarnitechAdminClient:
        """Get the admin client, creating and logging in if needed."""
        if self._admin is None or self._admin._session is None or self._admin._session.closed:
            if self._admin is not None:
                try:
                    await self._admin.close()
                except Exception:
                    pass
            self._admin = LarnitechAdminClient(host=self._host)
            self._logged_in = False

        if not self._logged_in:
            await self._admin.login()
            self._logged_in = True

        return self._admin

    async def _admin_call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call an admin API method with auto-reauth on failure."""
        admin = await self._ensure_admin()
        try:
            return await getattr(admin, method)(*args, **kwargs)
        except Exception:
            # Auth may have expired — re-login and retry once
            self._logged_in = False
            try:
                admin = await self._ensure_admin()
                return await getattr(admin, method)(*args, **kwargs)
            except Exception:
                raise

    async def _async_update_data(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Fetch module health data and HW configs from admin API."""
        try:
            raw = await self._admin_call(
                "_api_call",
                "Modules.getModules",
                ["", "", "", "", "-1", "", "id_asc"],
            )
            result: dict[str, dict[str, Any]] = {}
            if isinstance(raw, dict):
                for m in raw.get("modules", []):
                    mid = m.get("module_id", "")
                    if not mid:
                        continue
                    result[str(mid)] = {
                        "temp": _safe_int(m.get("module_temp")),
                        "temp_max": _safe_int(m.get("module_temp_max")),
                        "uptime": _safe_int(m.get("module_uptime")),
                        "status": m.get("module_status", 0),
                        "logic": m.get("module_logic_txt"),
                    }

            # Also refresh HW configs for tracked modules
            for mid in self._hw_module_ids:
                try:
                    hw = await self._admin_call(
                        "get_module_hw_config", mid
                    )
                    if mid in result:
                        result[mid]["hw_config"] = hw
                    else:
                        result[mid] = {"hw_config": hw}
                except Exception:
                    # Keep previous HW config on failure
                    if self.data and mid in self.data:
                        prev_hw = self.data[mid].get("hw_config")
                        if prev_hw:
                            result.setdefault(mid, {})["hw_config"] = prev_hw

            return result
        except Exception as err:
            if self.data:
                LOGGER.debug("Admin poll failed, keeping previous: %s", err)
                return self.data
            raise UpdateFailed(f"Admin API error: {err}") from err

    async def fetch_hw_config(self, module_id: str) -> dict[str, Any]:
        """Fetch hardware configuration for a single module."""
        self._hw_module_ids.add(module_id)
        return await self._admin_call("get_module_hw_config", module_id)

    async def fetch_all_hw_configs(
        self, module_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch HW config for multiple modules in one session.

        Also injects results into coordinator data so that entities
        created after this call can read values immediately (before
        the next periodic poll).
        """
        result: dict[str, dict[str, Any]] = {}
        for mid in module_ids:
            try:
                hw = await self._admin_call(
                    "get_module_hw_config", mid
                )
                result[mid] = hw
                # Track for periodic refresh
                self._hw_module_ids.add(mid)
            except Exception:
                LOGGER.debug("HW config failed for module %s", mid)

        # Inject into coordinator data so entities see it immediately
        if self.data is not None:
            for mid, hw in result.items():
                self.data.setdefault(mid, {})["hw_config"] = hw

        return result

    async def set_hw_config(
        self, module_id: str, hw_config: str
    ) -> dict:
        """Set hardware configuration for a module (raw, all pins)."""
        return await self._admin_call(
            "set_module_hw", module_id, hw_config
        )

    async def set_pin_type(
        self,
        module_id: str,
        connector: str,
        pin_num: str,
        hw_letter: str,
    ) -> dict:
        """Change a single pin's type, preserving all other pins."""
        result = await self._admin_call(
            "set_module_pin_type", module_id, connector, pin_num, hw_letter
        )
        # Trigger a data refresh so all entities see the change
        await self.async_request_refresh()
        return result

    async def set_pin_param(
        self,
        module_id: str,
        connector: str,
        pin_num: str,
        param_name: str,
        value: int,
    ) -> dict:
        """Set a single pin parameter (min, max, runtime, etc)."""
        result = await self._admin_call(
            "set_module_pin_param", module_id, connector, pin_num, param_name, value
        )
        await self.async_request_refresh()
        return result

    async def reboot_module(
        self, module_id: str, serial_dec: str
    ) -> bool:
        """Reboot a module."""
        return await self._admin_call(
            "reboot_module", module_id, serial_dec
        )

    async def async_shutdown(self) -> None:
        """Close the admin session."""
        if self._admin:
            try:
                await self._admin.close()
            except Exception:
                pass
            self._admin = None
            self._logged_in = False


def _safe_int(value: Any) -> int | None:
    """Safely convert to int, returning None on failure."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
