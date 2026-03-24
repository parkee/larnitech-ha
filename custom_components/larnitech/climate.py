"""Climate platform for the Larnitech integration."""

from __future__ import annotations

from typing import Any

from pylarnitech.codec import ACState
from pylarnitech.const import (
    AC_FAN_AUTO,
    AC_FAN_HIGH,
    AC_FAN_LOW,
    AC_FAN_MEDIUM,
    AC_FAN_NIGHT,
    AC_FAN_TURBO,
    AC_MODE_AUTO,
    AC_MODE_COOL,
    AC_MODE_DRY,
    AC_MODE_FAN_ONLY,
    AC_MODE_HEAT,
    DEVICE_TYPE_AC,
    DEVICE_TYPE_VALVE_HEATING,
)

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LarnitechConfigEntry
from .entity import LarnitechEntity

_LARNITECH_TO_HVAC_MODE = {
    AC_MODE_AUTO: HVACMode.AUTO,
    AC_MODE_HEAT: HVACMode.HEAT,
    AC_MODE_COOL: HVACMode.COOL,
    AC_MODE_FAN_ONLY: HVACMode.FAN_ONLY,
    AC_MODE_DRY: HVACMode.DRY,
}

_HVAC_TO_LARNITECH_MODE = {v: k for k, v in _LARNITECH_TO_HVAC_MODE.items()}

# Fan mode names: HA auto-capitalizes standard ones (auto/low/medium/high)
# but custom modes stay as-is, so we capitalize them ourselves.
FAN_TURBO = "Turbo"
FAN_NIGHT = "Night"

_LARNITECH_TO_FAN_MODE = {
    AC_FAN_AUTO: FAN_AUTO,
    AC_FAN_LOW: FAN_LOW,
    AC_FAN_MEDIUM: FAN_MEDIUM,
    AC_FAN_HIGH: FAN_HIGH,
    AC_FAN_TURBO: FAN_TURBO,
    AC_FAN_NIGHT: FAN_NIGHT,
}

_FAN_TO_LARNITECH = {v: k for k, v in _LARNITECH_TO_FAN_MODE.items()}

# Swing/vane positions: 0=Auto, 1-8=fixed positions
# Verified: horizontal swing has 0-8 (9 total positions)
SWING_AUTO = "Auto"
_SWING_MODES = [SWING_AUTO] + [str(i) for i in range(1, 9)]



async def async_setup_entry(
    hass: HomeAssistant,
    entry: LarnitechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Larnitech climate entities."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = []

    for device in coordinator.devices.values():
        if device.type == DEVICE_TYPE_AC:
            entities.append(LarnitechAC(coordinator, device))
        elif device.type == DEVICE_TYPE_VALVE_HEATING:
            entities.append(LarnitechValveHeating(coordinator, device))

    async_add_entities(entities)


class LarnitechAC(LarnitechEntity, ClimateEntity):
    """Representation of a Larnitech AC unit."""

    _attr_name = None
    _attr_translation_key = "larnitech_ac"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_TURBO, FAN_NIGHT]

    def __init__(self, coordinator, device):
        """Initialize the AC entity."""
        super().__init__(coordinator, device)
        t_min = int(device.extra.get("t-min", 16))
        t_delta = int(device.extra.get("t-delta", 16))
        self._attr_min_temp = t_min
        self._attr_max_temp = t_min + t_delta
        step = device.extra.get("t-step")
        self._attr_target_temperature_step = float(step) if step else 0.5

        # Pending state shadow for optimistic updates
        self._pending_state: ACState | None = None

        # All ACs get swing controls — the byte is always present in the
        # state. If the physical AC doesn't support vanes, it simply
        # ignores the values. 0 = Auto is always valid.
        self._attr_swing_modes = _SWING_MODES
        self._attr_swing_horizontal_modes = _SWING_MODES
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    def _get_ac_state(self) -> ACState:
        """Get AC state, preferring pending local state over coordinator."""
        if self._pending_state is not None:
            return self._pending_state
        status = self.device_status
        if status is None:
            return ACState.from_hex("")
        return ACState.from_hex(status.state)

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update — clear pending state."""
        self._pending_state = None
        super()._handle_coordinator_update()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        ac = self._get_ac_state()
        if not ac.power:
            return HVACMode.OFF
        return _LARNITECH_TO_HVAC_MODE.get(ac.mode, HVACMode.AUTO)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        ac = self._get_ac_state()
        if ac.temperature == 0:
            return None
        return float(ac.temperature)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        ac = self._get_ac_state()
        return _LARNITECH_TO_FAN_MODE.get(ac.fan, FAN_AUTO)

    @property
    def swing_mode(self) -> str | None:
        """Return the vertical vane position."""
        ac = self._get_ac_state()
        if ac.vane_vertical == 0:
            return SWING_AUTO
        return str(ac.vane_vertical)

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the horizontal vane position."""
        ac = self._get_ac_state()
        if ac.vane_horizontal == 0:
            return SWING_AUTO
        return str(ac.vane_horizontal)

    async def _async_send_ac_state(self, ac: ACState) -> None:
        """Send AC state and update optimistically."""
        await self.coordinator.client.set_device_status_raw(
            self._addr, ac.to_hex()
        )
        self._pending_state = ac
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        ac = self._get_ac_state()
        if hvac_mode == HVACMode.OFF:
            ac.power = False
        else:
            ac.power = True
            ac.mode = _HVAC_TO_LARNITECH_MODE.get(hvac_mode, AC_MODE_AUTO)
        await self._async_send_ac_state(ac)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        ac = self._get_ac_state()
        ac.temperature = float(temperature)
        await self._async_send_ac_state(ac)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        ac = self._get_ac_state()
        ac.fan = _FAN_TO_LARNITECH.get(fan_mode, AC_FAN_AUTO)
        await self._async_send_ac_state(ac)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical vane position."""
        ac = self._get_ac_state()
        ac.vane_vertical = 0 if swing_mode == SWING_AUTO else int(swing_mode)
        await self._async_send_ac_state(ac)

    async def async_set_swing_horizontal_mode(
        self, swing_mode: str
    ) -> None:
        """Set the horizontal vane position."""
        ac = self._get_ac_state()
        ac.vane_horizontal = 0 if swing_mode == SWING_AUTO else int(swing_mode)
        await self._async_send_ac_state(ac)

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        ac = self._get_ac_state()
        ac.power = True
        await self._async_send_ac_state(ac)

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        ac = self._get_ac_state()
        ac.power = False
        await self._async_send_ac_state(ac)


class LarnitechValveHeating(LarnitechEntity, ClimateEntity):
    """Representation of a Larnitech valve-heating device.

    Setpoint temperature is a configuration setting (read-only).
    Only on/off control is available via the API.
    """

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        status = self.device_status
        if status is None or status.state == "off":
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the current measured temperature."""
        status = self.device_status
        if status is None:
            return None
        return status.meas_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the target setpoint temperature (read-only)."""
        status = self.device_status
        if status is None:
            return None
        return status.setpoint_temp

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        status = self.device_status
        if status is None:
            return None
        attrs: dict[str, Any] = {}
        if status.mode_named:
            attrs["mode_named"] = status.mode_named
        modes = self._device.extra.get("modes")
        if modes:
            attrs["available_modes"] = [
                m.get("mode_named") for m in modes
            ]
        return attrs or None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (on/off only)."""
        state = "on" if hvac_mode == HVACMode.HEAT else "off"
        await self.coordinator.client.set_device_status(
            self._addr, {"state": state}
        )
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the heating on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the heating off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
