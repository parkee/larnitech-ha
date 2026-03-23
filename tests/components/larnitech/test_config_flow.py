"""Test the Larnitech config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pylarnitech.exceptions import (
    LarnitechAuthError,
    LarnitechConnectionError,
    LarnitechTimeoutError,
)

from custom_components.larnitech.const import (
    CONF_API_KEY,
    CONF_HTTP_PORT,
    CONF_WS_PORT,
    DOMAIN,
)

from .conftest import MOCK_API_KEY, MOCK_CONFIG_DATA, MOCK_HOST


@pytest.fixture
def mock_validate() -> AsyncMock:
    """Create a mock validate_connection."""
    return AsyncMock(return_value=10)


@pytest.fixture
def mock_get_serial() -> AsyncMock:
    """Create a mock _get_serial."""
    return AsyncMock(return_value="test_serial")


class TestConfigFlowUser:
    """Test the user config flow step."""

    async def test_show_form(self, hass) -> None:
        """Test that the form is shown on first step."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_create_entry_success(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test successful entry creation."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechClient"
            ) as mock_client_cls,
            patch(
                "custom_components.larnitech.config_flow.LarnitechConfigFlow._get_serial",
                return_value="test_serial",
            ),
        ):
            mock_client_cls.return_value.validate_connection = AsyncMock(
                return_value=10
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        assert result["title"] == f"Larnitech ({MOCK_HOST})"
        assert result["data"][CONF_API_KEY] == MOCK_API_KEY
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_invalid_auth(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test handling invalid authentication."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.validate_connection = AsyncMock(
                side_effect=LarnitechAuthError("Invalid key")
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

        # Recovery: provide valid credentials
        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechClient"
            ) as mock_client_cls,
            patch(
                "custom_components.larnitech.config_flow.LarnitechConfigFlow._get_serial",
                return_value=None,
            ),
        ):
            mock_client_cls.return_value.validate_connection = AsyncMock(
                return_value=10
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"

    async def test_cannot_connect(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test handling connection error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.validate_connection = AsyncMock(
                side_effect=LarnitechConnectionError("Refused")
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

        # Recovery
        with (
            patch(
                "custom_components.larnitech.config_flow.LarnitechClient"
            ) as mock_client_cls,
            patch(
                "custom_components.larnitech.config_flow.LarnitechConfigFlow._get_serial",
                return_value=None,
            ),
        ):
            mock_client_cls.return_value.validate_connection = AsyncMock(
                return_value=10
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )
            await hass.async_block_till_done()

        assert result["type"] == "create_entry"

    async def test_timeout(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test handling timeout error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.validate_connection = AsyncMock(
                side_effect=LarnitechTimeoutError("Timeout")
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_zero_devices_treated_as_auth_error(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test that zero devices is treated as invalid auth."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.validate_connection = AsyncMock(
                return_value=0
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )

        assert result["type"] == "form"
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

    async def test_unexpected_exception(
        self,
        hass,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test handling unexpected exception."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        with patch(
            "custom_components.larnitech.config_flow.LarnitechClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.validate_connection = AsyncMock(
                side_effect=RuntimeError("Something broke")
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_CONFIG_DATA,
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "unknown"}
