"""Tests for Qiara sensors."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE

from custom_components.qiara.sensor import QiaraBatterySensor
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
    sensor = QiaraBatterySensor(mock_coordinator, mock_entry, "sensor_1")
    
    assert sensor.available is True
    
    mock_coordinator.data["sensor_1"].available = False
    assert sensor.available is False
