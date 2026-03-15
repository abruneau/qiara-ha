"""Tests for Qiara binary sensors."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.qiara.binary_sensor import QiaraBinarySensor
from custom_components.qiara.models import QiaraSensorData

@pytest.fixture
def mock_coordinator():
    """Mock the coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "door_1": QiaraSensorData(
            id="door_1",
            name="Front Door",
            type="door",
            state="open",
            battery_level=85,
            available=True
        ),
        "motion_1": QiaraSensorData(
            id="motion_1",
            name="Living Room Motion",
            type="motion",
            state="clear",
            battery_level=100,
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

def test_binary_sensor_init(mock_coordinator, mock_entry):
    """Test binary sensor initialization."""
    sensor = QiaraBinarySensor(mock_coordinator, mock_entry, "door_1")
    
    assert sensor.name == "Front Door"
    assert sensor.unique_id == "test_entry_door_1_binary"
    assert sensor.device_class == BinarySensorDeviceClass.DOOR

def test_binary_sensor_is_on(mock_coordinator, mock_entry):
    """Test binary sensor is_on property."""
    sensor_door = QiaraBinarySensor(mock_coordinator, mock_entry, "door_1")
    sensor_motion = QiaraBinarySensor(mock_coordinator, mock_entry, "motion_1")
    
    assert sensor_door.is_on is True
    assert sensor_motion.is_on is False

def test_binary_sensor_attributes(mock_coordinator, mock_entry):
    """Test binary sensor extra state attributes."""
    sensor = QiaraBinarySensor(mock_coordinator, mock_entry, "door_1")
    
    assert sensor.extra_state_attributes["battery_level"] == 85
    assert "last_triggered" in sensor.extra_state_attributes

def test_binary_sensor_available(mock_coordinator, mock_entry):
    """Test binary sensor availability."""
    mock_coordinator.available = True
    sensor = QiaraBinarySensor(mock_coordinator, mock_entry, "door_1")

    assert sensor.available is True

    mock_coordinator.data["door_1"].available = False
    assert sensor.available is False

    mock_coordinator.data["door_1"].available = True
    mock_coordinator.available = False
    assert sensor.available is False
