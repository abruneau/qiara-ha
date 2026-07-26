"""Tests for Qiara sensors."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE

from custom_components.qiara.const import DOMAIN
from custom_components.qiara.sensor import QiaraBatterySensor, async_setup_entry
from custom_components.qiara.models import QiaraSensorData

@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "sensor_1": QiaraSensorData(
            id="sensor_1",
            name="Front Door",
            type="door",
            state="open",
            battery_level=85,
            available=True
        )
    }
    return coordinator

@pytest.fixture
def mock_entry():
    """Mock the config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry

def test_battery_sensor_init(mock_coordinator, mock_entry):
    """Test battery sensor initialization."""
    sensor = QiaraBatterySensor(mock_coordinator, mock_entry, "sensor_1")
    
    assert sensor.name == "Front Door Battery"
    assert sensor.unique_id == "test_entry_sensor_1_battery"
    assert sensor.device_class == SensorDeviceClass.BATTERY
    assert sensor.native_unit_of_measurement == PERCENTAGE

def test_battery_sensor_native_value(mock_coordinator, mock_entry):
    """Test battery sensor native value."""
    sensor = QiaraBatterySensor(mock_coordinator, mock_entry, "sensor_1")
    
    assert sensor.native_value == 85
    
    # Update battery level
    mock_coordinator.data["sensor_1"].battery_level = 42
    assert sensor.native_value == 42

def test_battery_sensor_available(mock_coordinator, mock_entry):
    """Test battery sensor availability."""
    mock_coordinator.last_update_success = True
    sensor = QiaraBatterySensor(mock_coordinator, mock_entry, "sensor_1")

    assert sensor.available is True

    mock_coordinator.data["sensor_1"].available = False
    assert sensor.available is False

    mock_coordinator.data["sensor_1"].available = True
    mock_coordinator.last_update_success = False
    assert sensor.available is False


@pytest.mark.asyncio
async def test_setup_removes_stale_temperature_entities(mock_entry):
    """Nodes that no longer report a temperature get their stale temperature entity removed."""
    coordinator = MagicMock()
    coordinator.data = {
        "10": QiaraSensorData(
            id="10", name="Siren", type="siren", temperature=24.0, battery_level=90
        ),
        "12": QiaraSensorData(
            id="12", name="Door", type="door", battery_level=100
        ),  # sentinel-only node -> no temperature
    }
    hass = MagicMock()
    hass.data = {DOMAIN: {mock_entry.entry_id: coordinator}}

    live_temp = MagicMock(
        domain="sensor",
        unique_id=f"{mock_entry.entry_id}_10_temperature",
        entity_id="sensor.siren_temperature",
    )
    stale_temp = MagicMock(
        domain="sensor",
        unique_id=f"{mock_entry.entry_id}_12_temperature",
        entity_id="sensor.door_temperature",
    )
    battery = MagicMock(
        domain="sensor",
        unique_id=f"{mock_entry.entry_id}_12_battery",
        entity_id="sensor.door_battery",
    )
    ent_reg = MagicMock()

    added: list = []
    with patch(
        "custom_components.qiara.sensor.er.async_get", return_value=ent_reg
    ), patch(
        "custom_components.qiara.sensor.er.async_entries_for_config_entry",
        return_value=[live_temp, stale_temp, battery],
    ):
        await async_setup_entry(hass, mock_entry, added.extend)

    # Only the stale temperature entity is removed; the live one and the
    # battery entity are left untouched.
    ent_reg.async_remove.assert_called_once_with("sensor.door_temperature")
