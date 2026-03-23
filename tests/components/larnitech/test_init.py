"""Test the Larnitech integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pylarnitech.exceptions import (
    LarnitechAuthError,
    LarnitechConnectionError,
)

from custom_components.larnitech.const import DOMAIN

from .conftest import MOCK_CONFIG_DATA, MOCK_DEVICES, MOCK_STATUSES


@pytest.fixture
def mock_config_entry(hass):
    """Create a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Larnitech (192.168.4.100)",
        data=MOCK_CONFIG_DATA,
        source="user",
    )
    entry.add_to_hass(hass)
    return entry


class TestSetup:
    """Test integration setup."""

    async def test_setup_success(self, hass, mock_client, mock_config_entry) -> None:
        """Test successful setup."""
        with patch(
            "custom_components.larnitech.LarnitechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert mock_config_entry.runtime_data is not None
        assert mock_client.validate_connection.called

    async def test_setup_auth_failure(self, hass, mock_client, mock_config_entry) -> None:
        """Test setup with authentication failure."""
        mock_client.validate_connection.side_effect = LarnitechAuthError("Invalid key")

        with patch(
            "custom_components.larnitech.LarnitechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False

    async def test_setup_connection_failure(self, hass, mock_client, mock_config_entry) -> None:
        """Test setup with connection failure (triggers retry)."""
        mock_client.validate_connection.side_effect = LarnitechConnectionError("Refused")

        with patch(
            "custom_components.larnitech.LarnitechClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # ConfigEntryNotReady causes retry, entry state should reflect this
        assert result is False

    async def test_unload(self, hass, mock_client, mock_config_entry) -> None:
        """Test unloading the integration."""
        with patch(
            "custom_components.larnitech.LarnitechClient",
            return_value=mock_client,
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert mock_client.disconnect.called
