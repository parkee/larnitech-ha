"""DataUpdateCoordinator for the Larnitech integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pylarnitech import LarnitechClient, LarnitechDevice, LarnitechDeviceStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type LarnitechConfigEntry = ConfigEntry[LarnitechCoordinator]

# Fallback poll interval. WebSocket push handles most updates in real-time,
# but polling catches anything missed (e.g. if WS connection drops).
_POLL_INTERVAL = timedelta(seconds=30)


class LarnitechCoordinator(DataUpdateCoordinator[dict[str, LarnitechDeviceStatus]]):
    """Coordinator for Larnitech devices.

    Primary: WebSocket push (port 8080) for real-time status changes.
    Fallback: HTTP polling every 30s via getAllDevicesStatus.

    The Larnitech WebSocket pushes 'deviceStatusChange' messages
    whenever any device state changes (from app, physical controls, etc).
    The WS connection must have an initial request sent to "subscribe"
    — after that, all changes are pushed automatically.
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
            update_interval=_POLL_INTERVAL,
        )
        self.client = client
        self.devices: dict[str, LarnitechDevice] = {}
        self.module_models: dict[str, str] = {}
        self._unsub_ws: list[Any] = []

    async def _async_setup(self) -> None:
        """Fetch initial device list and set up WebSocket push."""
        device_list = await self.client.get_devices()
        self.devices = {d.addr: d for d in device_list}
        LOGGER.debug("Loaded %d devices from controller", len(self.devices))

        # Set up WebSocket for real-time push
        try:
            await self.client.connect(auto_reconnect=True)
            self._unsub_ws.append(
                self.client.on_status_update(self._handle_ws_push)
            )
            LOGGER.debug("WebSocket connected for push updates")

            # Send an initial request to "subscribe" to push events.
            # The Seasocks server starts pushing deviceStatusChange
            # messages after the first request on the WS connection.
            await self.client.ws_send_json(
                {"requestType": "getAllDevicesStatus"}
            )
            LOGGER.debug("WebSocket subscribed to status changes")
        except Exception:
            LOGGER.info(
                "WebSocket not available, using HTTP polling only"
            )

    async def _async_update_data(
        self,
    ) -> dict[str, LarnitechDeviceStatus]:
        """Fetch latest statuses via HTTP API (fallback poll)."""
        try:
            statuses = await self.client.get_all_statuses()
        except Exception as err:
            # If we have previous data, log the error but don't crash.
            # The controller sometimes returns bad responses when busy.
            if self.data:
                LOGGER.debug(
                    "Poll failed, keeping previous data: %s", err
                )
                return self.data
            raise UpdateFailed(
                f"Error fetching device statuses: {err}"
            ) from err
        if not statuses:
            return self.data or {}
        return {s.addr: s for s in statuses}

    @callback
    def _handle_ws_push(self, data: dict[str, Any]) -> None:
        """Handle a real-time status push from WebSocket.

        Push messages have requestType 'deviceStatusChange' with the
        same 'status' structure as getDeviceStatus responses.
        """
        if not isinstance(data, dict):
            return
        status = data.get("status")
        if not isinstance(status, dict):
            return
        addr = status.get("addr")
        if not addr:
            return

        device_status = LarnitechDeviceStatus.from_dict(status)
        current = dict(self.data) if self.data is not None else {}
        current[addr] = device_status
        self.async_set_updated_data(current)

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
