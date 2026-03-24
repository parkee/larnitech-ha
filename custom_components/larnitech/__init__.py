"""The Larnitech integration."""

from __future__ import annotations

from pylarnitech import LarnitechClient

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .admin_coordinator import LarnitechAdminCoordinator
from .const import (
    CONF_API_KEY,
    CONF_HTTP_PORT,
    DEFAULT_HTTP_PORT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import LarnitechConfigEntry, LarnitechCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Larnitech integration."""
    from .services import async_setup_services

    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
) -> bool:
    """Set up Larnitech from a config entry."""
    host = entry.data[CONF_HOST]

    client = LarnitechClient(
        host=host,
        api_key=entry.data[CONF_API_KEY],
        http_port=entry.data.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT),
    )

    # Validate connection
    try:
        device_count = await client.validate_connection()
    except Exception as err:
        err_str = str(err).lower()
        if "auth" in err_str or "key" in err_str:
            raise ConfigEntryAuthFailed(
                f"Invalid API key for {host}"
            ) from err
        raise ConfigEntryNotReady(
            f"Cannot connect to {host}: {err}"
        ) from err

    if device_count == 0:
        LOGGER.warning(
            "No devices found on %s; API key may be incorrect", host
        )

    # Register the controller as a device (hub)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Larnitech ({host})",
        manufacturer="Larnitech",
        model="DE-MG",
    )

    # Fetch module info from admin panel
    from pylarnitech.admin import LarnitechAdminClient

    module_info: dict = {}
    try:
        admin = LarnitechAdminClient(host=host)
        await admin.login()
        module_info = await admin.get_modules()
        try:
            extra = await admin.get_modules_extra_data()
            locations = (
                extra.get("locations", {})
                if isinstance(extra, dict)
                else {}
            )
            for mid, loc in locations.items():
                if str(mid) in module_info and isinstance(loc, dict):
                    primary = loc.get("name", "")
                    if primary.startswith("/"):
                        primary = primary.rsplit("/", 1)[-1]
                    module_info[str(mid)]["primary_area"] = primary
        except Exception:
            LOGGER.debug("Could not load module extra data")
        await admin.close()
        LOGGER.debug("Loaded %d module info from admin panel", len(module_info))
    except Exception:
        module_info = {}
        LOGGER.debug("Could not load module info from admin panel")

    # Create device status coordinator (HTTP + WebSocket push)
    coordinator = LarnitechCoordinator(hass, entry, client)
    coordinator.module_info = module_info
    await coordinator.async_config_entry_first_refresh()

    # Create admin coordinator for module health (polls every 5 min)
    admin_coordinator = LarnitechAdminCoordinator(hass, host)
    await admin_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Store admin coordinator in hass.data for access by platform entities
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "admin_coordinator": admin_coordinator,
    }

    # Forward to entity platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up on HA shutdown
    async def _async_shutdown(_event: object) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
) -> bool:
    """Unload a Larnitech config entry."""
    coordinator: LarnitechCoordinator = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
