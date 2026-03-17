"""Tests for Qiara alarm control panel."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.exceptions import HomeAssistantError, UpdateFailed

from custom_components.qiara.alarm_control_panel import QiaraAlarmControlPanel
from custom_components.qiara.const import SYSTEM_MODE_DAY, SYSTEM_MODE_NIGHT


@pytest.fixture
def mock_coordinator():
    """Mock the coordinator with a mocked API."""
    coordinator = MagicMock()
    coordinator.available = True
    coordinator.api = MagicMock()
    coordinator.api.async_arm_system = AsyncMock(return_value=True)
    coordinator.api.async_disarm_system = AsyncMock(return_value=True)
    return coordinator


@pytest.fixture
def mock_entry():
    """Mock the config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


@pytest.fixture
def alarm_panel(mock_coordinator, mock_entry):
    """Create a QiaraAlarmControlPanel instance."""
    return QiaraAlarmControlPanel(mock_coordinator, mock_entry)


def test_alarm_panel_init(alarm_panel, mock_entry):
    """Test alarm control panel initialization."""
    assert alarm_panel.unique_id == f"{mock_entry.entry_id}_alarm_control_panel"
    assert alarm_panel.name == "Qiara Alarm"


def test_alarm_panel_initial_state(alarm_panel):
    """Test alarm control panel starts in DISARMED state."""
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


def test_alarm_panel_supported_features(alarm_panel):
    """Test supported features include ARM_HOME and ARM_NIGHT."""
    features = alarm_panel.supported_features
    assert features & AlarmControlPanelEntityFeature.ARM_HOME
    assert features & AlarmControlPanelEntityFeature.ARM_NIGHT


@pytest.mark.asyncio
async def test_alarm_arm_home(alarm_panel, mock_coordinator):
    """Test arming in home (day) mode calls async_arm_system with 'day' and notifies HA."""
    with patch.object(alarm_panel, "async_write_ha_state") as mock_write:
        await alarm_panel.async_alarm_arm_home()

    mock_coordinator.api.async_arm_system.assert_called_once_with(SYSTEM_MODE_DAY)
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_alarm_arm_night(alarm_panel, mock_coordinator):
    """Test arming in night mode calls async_arm_system with 'night' and notifies HA."""
    with patch.object(alarm_panel, "async_write_ha_state") as mock_write:
        await alarm_panel.async_alarm_arm_night()

    mock_coordinator.api.async_arm_system.assert_called_once_with(SYSTEM_MODE_NIGHT)
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_NIGHT
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_alarm_disarm(alarm_panel, mock_coordinator):
    """Test disarming calls async_disarm_system, sets state to DISARMED, and notifies HA."""
    # First arm it so we can verify disarm actually changes state
    await alarm_panel.async_alarm_arm_home()
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME

    with patch.object(alarm_panel, "async_write_ha_state") as mock_write:
        await alarm_panel.async_alarm_disarm()

    mock_coordinator.api.async_disarm_system.assert_called_once()
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_alarm_arm_home_error(alarm_panel, mock_coordinator):
    """Test that arm_home raises HomeAssistantError on API failure."""
    mock_coordinator.api.async_arm_system = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(HomeAssistantError):
        await alarm_panel.async_alarm_arm_home()

    # State should remain unchanged
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_arm_night_error(alarm_panel, mock_coordinator):
    """Test that arm_night raises HomeAssistantError on API failure."""
    mock_coordinator.api.async_arm_system = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(HomeAssistantError):
        await alarm_panel.async_alarm_arm_night()

    # State should remain unchanged
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_disarm_error(alarm_panel, mock_coordinator):
    """Test that disarm raises HomeAssistantError on API failure and preserves armed state."""
    # Arm first so we can verify a failed disarm doesn't change the state
    await alarm_panel.async_alarm_arm_home()
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME

    mock_coordinator.api.async_disarm_system = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(HomeAssistantError):
        await alarm_panel.async_alarm_disarm()

    # State should remain ARMED_HOME, not flip to DISARMED
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME


@pytest.mark.asyncio
async def test_alarm_arm_home_update_failed_not_double_wrapped(alarm_panel, mock_coordinator):
    """Test that UpdateFailed from API layer is NOT double-wrapped in the error message (H1 regression guard)."""
    mock_coordinator.api.async_arm_system = AsyncMock(
        side_effect=UpdateFailed("Failed to arm system: connection timeout")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await alarm_panel.async_alarm_arm_home()

    error_msg = str(exc_info.value)
    assert "Failed to arm system: connection timeout" in error_msg
    assert error_msg.count("Failed to arm system") == 1, "Message should not be double-wrapped"
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_arm_home_node_not_yet_discovered(alarm_panel, mock_coordinator):
    """Test arm_home when alarm node has not been discovered yet (_alarm_node_id is None path)."""
    mock_coordinator.api.async_arm_system = AsyncMock(
        side_effect=UpdateFailed("Alarm node not yet discovered — wait for first coordinator refresh")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await alarm_panel.async_alarm_arm_home()

    assert "Alarm node not yet discovered" in str(exc_info.value)
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


def test_alarm_panel_availability(alarm_panel, mock_coordinator):
    """Test alarm panel availability follows coordinator availability."""
    mock_coordinator.available = True
    assert alarm_panel.available is True

    mock_coordinator.available = False
    assert alarm_panel.available is False
