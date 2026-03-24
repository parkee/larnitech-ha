"""Admin API coordinator for module health and configuration data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pylarnitech.admin import LarnitechAdminClient

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

# Poll module health every 5 minutes (temp, uptime, status)
_ADMIN_POLL_INTERVAL = timedelta(minutes=5)


class LarnitechAdminCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for Larnitech admin panel data.

    Polls Modules.getModules every 5 minutes to get live module
    health data (temperature, uptime, status, max temp).
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
        self.hw_configs: dict[str, dict[str, Any]] = {}

    async def _async_update_data(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Fetch module health data from admin API."""
        admin = LarnitechAdminClient(host=self._host)
        try:
            await admin.login()
            modules = await admin.get_modules()
            # get_modules returns {mid: {model, serial, serial_dec, firmware}}
            # We need more data — call getModules directly for temp/uptime
            raw = await admin._api_call(
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
            return result
        except Exception as err:
            if self.data:
                LOGGER.debug("Admin poll failed, keeping previous: %s", err)
                return self.data
            raise UpdateFailed(f"Admin API error: {err}") from err
        finally:
            await admin.close()

    async def fetch_hw_config(self, module_id: str) -> dict[str, Any]:
        """Fetch hardware configuration for a single module."""
        admin = LarnitechAdminClient(host=self._host)
        try:
            await admin.login()
            return await admin.get_module_hw_config(module_id)
        finally:
            await admin.close()

    async def set_hw_config(
        self, module_id: str, hw_config: str
    ) -> bool:
        """Set hardware configuration for a module."""
        admin = LarnitechAdminClient(host=self._host)
        try:
            await admin.login()
            return await admin.set_module_hw(module_id, hw_config)
        finally:
            await admin.close()


def _safe_int(value: Any) -> int | None:
    """Safely convert to int, returning None on failure."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
