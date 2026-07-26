"""Tests for the Qiara data update coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.qiara.coordinator import QiaraDataUpdateCoordinator
from custom_components.qiara.models import QiaraSensorData


@pytest.fixture
def mock_api():
    """Mock the Qiara API."""
    api = MagicMock()
    api.async_get_sensors = AsyncMock(return_value=[])
    api.async_get_alarm_state = AsyncMock(return_value="off")
    return api


@pytest.fixture
def mock_entry():
    """Mock the config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    return entry


def test_coordinator_passes_config_entry_explicitly(mock_api, mock_entry):
    """The entry must reach the base class, not be resolved from a ContextVar.

    Regression guard: HA only populates `config_entries.current_entry` inside
    its config entry setup context. A coordinator built on any other code path
    (a manual reload, for instance) would otherwise get config_entry=None,
    which makes async_config_entry_first_refresh raise ConfigEntryError and
    skips the async_shutdown unload hook.
    """
    coordinator = QiaraDataUpdateCoordinator(
        MagicMock(spec=HomeAssistant), mock_api, mock_entry
    )

    assert coordinator.config_entry is mock_entry


@pytest.mark.asyncio
async def test_update_data_keys_sensors_by_id_and_adds_alarm_state(mock_api, mock_entry):
    """_async_update_data returns sensors keyed by id plus the alarm_state key."""
    mock_api.async_get_sensors = AsyncMock(
        return_value=[
            QiaraSensorData(id="7", name="Front Door", type="door"),
            QiaraSensorData(id="9", name="Hall Motion", type="motion"),
        ]
    )
    mock_api.async_get_alarm_state = AsyncMock(return_value="day_armed")

    coordinator = QiaraDataUpdateCoordinator(
        MagicMock(spec=HomeAssistant), mock_api, mock_entry
    )
    data = await coordinator._async_update_data()

    assert set(data) == {"7", "9", "alarm_state"}
    assert data["alarm_state"] == "day_armed"
    assert isinstance(data["7"], QiaraSensorData)
    assert data["7"].name == "Front Door"
