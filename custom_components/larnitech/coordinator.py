"""DataUpdateCoordinator for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech import LarnitechClient, LarnitechDevice, LarnitechDeviceStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type LarnitechConfigEntry = ConfigEntry[LarnitechCoordinator]


class LarnitechCoordinator(DataUpdateCoordinator[dict[str, LarnitechDeviceStatus]]):
    """Coordinator for Larnitech devices.

    Uses HTTP API for commands (reliable request-response).
    Uses WebSocket for real-time push updates when connected.
    Falls back to HTTP polling when WebSocket is unavailable.
    """

    config_entry: LarnitechConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LarnitechConfigEntry,
        client: LarnitechClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
        )
        self.client = client
        self.devices: dict[str, LarnitechDevice] = {}
        self._unsub_ws: list[Any] = []

    async def _async_setup(self) -> None:
        """Fetch initial device list and set up WebSocket push."""
        device_list = await self.client.get_devices()
        self.devices = {d.addr: d for d in device_list}
        LOGGER.debug("Loaded %d devices from controller", len(self.devices))

        # Try to establish WebSocket for push updates
        try:
            await self.client.connect(auto_reconnect=True)
            self._unsub_ws.append(
                self.client.on_status_update(self._handle_ws_update)
            )
            self._unsub_ws.append(
                self.client.on_disconnect(self._handle_ws_disconnect)
            )
            LOGGER.debug("WebSocket connected for push updates")
        except Exception:
            LOGGER.debug(
                "WebSocket not available, will use HTTP polling",
                exc_info=True,
            )

    async def _async_update_data(
        self,
    ) -> dict[str, LarnitechDeviceStatus]:
        """Fetch latest statuses via HTTP API.

        Called on first refresh and when manually requested.
        When WebSocket is pushing updates, this is called less frequently.
        """
        try:
            statuses = await self.client.get_all_statuses()
        except Exception as err:
            raise UpdateFailed(f"Error fetching device statuses: {err}") from err
        return {s.addr: s for s in statuses}

    @callback
    def _handle_ws_update(self, data: dict[str, Any]) -> None:
        """Handle a status push from WebSocket."""
        status = data.get("status")
        if not status:
            return
        addr = status.get("addr")
        if not addr:
            return

        # Update our data with the new status
        device_status = LarnitechDeviceStatus.from_dict(status)
        if self.data is not None:
            self.data[addr] = device_status
            self.async_set_updated_data(self.data)

    @callback
    def _handle_ws_disconnect(self) -> None:
        """Handle WebSocket disconnect."""
        LOGGER.warning("WebSocket disconnected, falling back to polling")

    async def async_shutdown(self) -> None:
        """Clean up on shutdown."""
        for unsub in self._unsub_ws:
            unsub()
        self._unsub_ws.clear()
        await self.client.disconnect()

    def get_device(self, addr: str) -> LarnitechDevice | None:
        """Get a device by address."""
        return self.devices.get(addr)

    def get_status(self, addr: str) -> LarnitechDeviceStatus | None:
        """Get the latest status for a device."""
        if self.data is None:
            return None
        return self.data.get(addr)
