"""Test the Larnitech config flow (menu: native / http, plus reconfigure)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from pylarnitech.exceptions import (
    LarnitechAuthError,
    LarnitechConnectionError,
    LarnitechTimeoutError,
)

from custom_components.larnitech.const import (
    CONF_ACCESS_KEY,
    CONF_API_KEY,
    CONF_CONNECTION_MODE,
    CONNECTION_MODE_HTTP,
    CONNECTION_MODE_NATIVE,
    DOMAIN,
)

from .conftest import MOCK_API_KEY, MOCK_CONFIG_DATA, MOCK_HOST

MOCK_NATIVE_INPUT = {"host": MOCK_HOST, "access_key": "0383982796169537"}
MOCK_HTTP_INPUT = {
    "host": MOCK_HOST,
    "api_key": MOCK_API_KEY,
    "ws_port": 8080,
    "http_port": 8888,
}


def _patch_serial(value: str | None = "test_serial"):
    return patch(
        "custom_components.larnitech.config_flow.LarnitechConfigFlow._get_serial",
        return_value=value,
    )


async def _start(hass, source="user"):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": source})


class TestMenu:
    async def test_show_menu(self, hass) -> None:
        """First step is a transport menu."""
        result = await _start(hass)
        assert result["type"] == "menu"
        assert result["step_id"] == "user"
        assert set(result["menu_options"]) == {
            CONNECTION_MODE_NATIVE,
            CONNECTION_MODE_HTTP,
        }


class TestHttpFlow:
    async def test_create_entry_success(self, hass, mock_setup_entry) -> None:
        """HTTP path creates an entry tagged http."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_HTTP}
        )
        assert result["step_id"] == CONNECTION_MODE_HTTP

        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechClient"
            ) as mock_cls,
            _patch_serial(),
        ):
            mock_cls.return_value.validate_connection = AsyncMock(return_value=10)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_HTTP_INPUT
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        assert result["title"] == f"Larnitech ({MOCK_HOST})"
        assert result["data"][CONF_API_KEY] == MOCK_API_KEY
        assert result["data"][CONF_CONNECTION_MODE] == CONNECTION_MODE_HTTP
        assert len(mock_setup_entry.mock_calls) == 1

    @pytest.mark.parametrize(
        ("side_effect", "expected"),
        [
            (LarnitechAuthError("x"), "invalid_auth"),
            (LarnitechConnectionError("x"), "cannot_connect"),
            (LarnitechTimeoutError("x"), "cannot_connect"),
            (RuntimeError("x"), "unknown"),
        ],
    )
    async def test_errors(self, hass, side_effect, expected) -> None:
        """Validation errors are surfaced on the http form."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_HTTP}
        )
        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_cls:
            mock_cls.return_value.validate_connection = AsyncMock(
                side_effect=side_effect
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_HTTP_INPUT
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": expected}

    async def test_zero_devices_invalid_auth(self, hass) -> None:
        """Zero devices is treated as invalid auth."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_HTTP}
        )
        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_cls:
            mock_cls.return_value.validate_connection = AsyncMock(return_value=0)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_HTTP_INPUT
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}


class TestNativeFlow:
    async def test_create_entry_with_key(self, hass, mock_setup_entry) -> None:
        """Native path with an explicit access key."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_NATIVE}
        )
        assert result["step_id"] == CONNECTION_MODE_NATIVE

        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechNativeClient"
            ) as mock_cls,
            _patch_serial(),
        ):
            inst = mock_cls.return_value
            inst.validate_connection = AsyncMock(return_value=10)
            inst.disconnect = AsyncMock()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_NATIVE_INPUT
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        assert result["data"][CONF_CONNECTION_MODE] == CONNECTION_MODE_NATIVE
        assert result["data"][CONF_ACCESS_KEY] == "0383982796169537"
        assert inst.disconnect.called
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_auto_fetch_key(self, hass, mock_setup_entry) -> None:
        """Blank access key is auto-fetched from the admin panel."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_NATIVE}
        )
        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechNativeClient"
            ) as mock_cls,
            patch(
                "custom_components.larnitech.config_flow."
                "LarnitechConfigFlow._fetch_access_key",
                return_value="FETCHEDKEY0000000",
            ),
            _patch_serial(None),
        ):
            inst = mock_cls.return_value
            inst.validate_connection = AsyncMock(return_value=5)
            inst.disconnect = AsyncMock()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": MOCK_HOST, "access_key": ""}
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ACCESS_KEY] == "FETCHEDKEY0000000"

    async def test_auto_fetch_fails(self, hass) -> None:
        """If the key can't be fetched and none given, surface an error."""
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_NATIVE}
        )
        with patch(
            "custom_components.larnitech.config_flow."
            "LarnitechConfigFlow._fetch_access_key",
            return_value="",
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": MOCK_HOST, "access_key": ""}
            )
        assert result["type"] == "form"
        assert result["errors"] == {CONF_ACCESS_KEY: "access_key_required"}


class TestReconfigure:
    async def test_switch_http_to_native(self, hass, mock_setup_entry) -> None:
        """Reconfigure an existing HTTP entry to native, keeping the same entry."""
        entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title=f"Larnitech ({MOCK_HOST})",
            data={**MOCK_CONFIG_DATA, CONF_CONNECTION_MODE: CONNECTION_MODE_HTTP},
            source="user",
            unique_id="test_serial",
        )
        entry.add_to_hass(hass)
        entry_id = entry.entry_id

        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] == "menu"
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONNECTION_MODE_NATIVE}
        )
        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechNativeClient"
            ) as mock_cls,
            _patch_serial("test_serial"),
        ):
            inst = mock_cls.return_value
            inst.validate_connection = AsyncMock(return_value=10)
            inst.disconnect = AsyncMock()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], MOCK_NATIVE_INPUT
            )
            await hass.async_block_till_done()

        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"
        # Same entry preserved, now native.
        updated = hass.config_entries.async_get_entry(entry_id)
        assert updated.data[CONF_CONNECTION_MODE] == CONNECTION_MODE_NATIVE
        assert updated.data[CONF_ACCESS_KEY] == "0383982796169537"
