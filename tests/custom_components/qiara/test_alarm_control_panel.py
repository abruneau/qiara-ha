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
    coordinator.data = {}
    coordinator.api = MagicMock()
    coordinator.api.async_arm_system = AsyncMock(return_value=True)
    coordinator.api.async_disarm_system = AsyncMock(return_value=True)
    coordinator.api.async_get_alarm_state = AsyncMock(return_value=None)
    coordinator.async_update_listeners = MagicMock()
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
    with patch.object(alarm_panel, "async_write_ha_state") as mock_write, patch.object(
        alarm_panel, "_async_confirm_state", AsyncMock()
    ) as mock_confirm:
        await alarm_panel.async_alarm_arm_home()

    mock_coordinator.api.async_arm_system.assert_called_once_with(SYSTEM_MODE_DAY)
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME
    assert mock_write.call_count == 2
    mock_confirm.assert_called_once()


@pytest.mark.asyncio
async def test_alarm_arm_home_shows_pending_state_first(alarm_panel):
    """Test that arm_home shows the ARMING pending state before the final ARMED_HOME state."""
    seen_states = []

    def record_state() -> None:
        seen_states.append(alarm_panel.alarm_state)

    with patch.object(
        alarm_panel, "async_write_ha_state", side_effect=record_state
    ), patch.object(alarm_panel, "_async_confirm_state", AsyncMock()):
        await alarm_panel.async_alarm_arm_home()

    assert seen_states == [
        AlarmControlPanelState.ARMING,
        AlarmControlPanelState.ARMED_HOME,
    ]


@pytest.mark.asyncio
async def test_alarm_arm_night(alarm_panel, mock_coordinator):
    """Test arming in night mode calls async_arm_system with 'night' and notifies HA."""
    with patch.object(alarm_panel, "async_write_ha_state") as mock_write, patch.object(
        alarm_panel, "_async_confirm_state", AsyncMock()
    ) as mock_confirm:
        await alarm_panel.async_alarm_arm_night()

    mock_coordinator.api.async_arm_system.assert_called_once_with(SYSTEM_MODE_NIGHT)
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_NIGHT
    assert mock_write.call_count == 2
    mock_confirm.assert_called_once()


@pytest.mark.asyncio
async def test_alarm_disarm(alarm_panel, mock_coordinator):
    """Test disarming calls async_disarm_system, sets state to DISARMED, and notifies HA."""
    with patch.object(alarm_panel, "_async_confirm_state", AsyncMock()):
        # First arm it so we can verify disarm actually changes state
        await alarm_panel.async_alarm_arm_home()
        assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME

        with patch.object(alarm_panel, "async_write_ha_state") as mock_write:
            await alarm_panel.async_alarm_disarm()

    mock_coordinator.api.async_disarm_system.assert_called_once()
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED
    assert mock_write.call_count == 2


@pytest.mark.asyncio
async def test_alarm_arm_home_error(alarm_panel, mock_coordinator):
    """Test that arm_home raises HomeAssistantError on API failure and clears the optimistic override."""
    mock_coordinator.api.async_arm_system = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(HomeAssistantError):
        await alarm_panel.async_alarm_arm_home()

    # State should fall back to coordinator truth (no data yet -> DISARMED), not stay stuck ARMING
    assert alarm_panel._optimistic_state is None
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_arm_night_error(alarm_panel, mock_coordinator):
    """Test that arm_night raises HomeAssistantError on API failure and clears the optimistic override."""
    mock_coordinator.api.async_arm_system = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(HomeAssistantError):
        await alarm_panel.async_alarm_arm_night()

    assert alarm_panel._optimistic_state is None
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_disarm_error(alarm_panel, mock_coordinator):
    """Test that disarm raises HomeAssistantError on API failure and preserves the last confirmed armed state."""
    with patch.object(alarm_panel, "_async_confirm_state", AsyncMock()):
        # Arm first so we can verify a failed disarm doesn't silently flip to DISARMED
        await alarm_panel.async_alarm_arm_home()
        assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME

        mock_coordinator.api.async_disarm_system = AsyncMock(side_effect=Exception("API error"))

        with pytest.raises(HomeAssistantError):
            await alarm_panel.async_alarm_disarm()

    # Optimistic override is cleared; coordinator has no data yet so it falls back to DISARMED
    # (the coordinator's periodic poll is the source of truth for what actually happened on the device).
    assert alarm_panel._optimistic_state is None


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


def test_alarm_state_from_coordinator_data_day(alarm_panel, mock_coordinator):
    """Test alarm_state returns ARMED_HOME when coordinator data has alarm_state='day'."""
    mock_coordinator.data = {"alarm_state": "day"}
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME


def test_alarm_state_from_coordinator_data_night(alarm_panel, mock_coordinator):
    """Test alarm_state returns ARMED_NIGHT when coordinator data has alarm_state='night'."""
    mock_coordinator.data = {"alarm_state": "night"}
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_NIGHT


def test_alarm_state_from_coordinator_data_off(alarm_panel, mock_coordinator):
    """Test alarm_state returns DISARMED when coordinator data has alarm_state='off'."""
    mock_coordinator.data = {"alarm_state": "off"}
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


def test_alarm_state_fallback_to_optimistic(alarm_panel, mock_coordinator):
    """Test alarm_state falls back to _optimistic_state when coordinator data has no alarm_state key."""
    mock_coordinator.data = {}
    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED
    alarm_panel._optimistic_state = AlarmControlPanelState.ARMED_HOME
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME


def test_alarm_state_optimistic_overrides_stale_coordinator_data(alarm_panel, mock_coordinator):
    """Regression test: a fresh optimistic value must win over stale coordinator data.

    Before this fix, alarm_state always preferred coordinator.data["alarm_state"] when
    present, so the widget kept showing the pre-command state until the next ~60s poll.
    """
    mock_coordinator.data = {"alarm_state": "off"}
    alarm_panel._optimistic_state = AlarmControlPanelState.ARMED_HOME
    assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME


@pytest.mark.asyncio
async def test_confirm_state_success_updates_coordinator_and_clears_optimistic(
    alarm_panel, mock_coordinator
):
    """Test that a matching confirm poll writes coordinator data and clears the optimistic override."""
    alarm_panel._optimistic_state = AlarmControlPanelState.ARMED_HOME
    mock_coordinator.data = {"alarm_state": "off"}
    mock_coordinator.api.async_get_alarm_state = AsyncMock(return_value="day_armed")

    with patch(
        "custom_components.qiara.alarm_control_panel.asyncio.sleep", AsyncMock()
    ), patch.object(alarm_panel, "async_write_ha_state") as mock_write:
        await alarm_panel._async_confirm_state(("day", "day_armed"))

    assert mock_coordinator.data["alarm_state"] == "day_armed"
    mock_coordinator.async_update_listeners.assert_called_once()
    assert alarm_panel._optimistic_state is None
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_state_retries_then_confirms(alarm_panel, mock_coordinator):
    """Test that the confirm loop keeps polling until the device reports the expected state."""
    alarm_panel._optimistic_state = AlarmControlPanelState.ARMED_NIGHT
    mock_coordinator.data = {"alarm_state": "off"}
    mock_coordinator.api.async_get_alarm_state = AsyncMock(
        side_effect=["off", "off", "night_armed"]
    )

    with patch("custom_components.qiara.alarm_control_panel.asyncio.sleep", AsyncMock()):
        await alarm_panel._async_confirm_state(("night", "night_armed"))

    assert mock_coordinator.api.async_get_alarm_state.call_count == 3
    assert alarm_panel._optimistic_state is None


@pytest.mark.asyncio
async def test_confirm_state_timeout_keeps_optimistic(alarm_panel, mock_coordinator):
    """Test that the confirm loop gives up after its attempt budget without clearing the optimistic state."""
    alarm_panel._optimistic_state = AlarmControlPanelState.ARMED_HOME
    mock_coordinator.data = {"alarm_state": "off"}
    mock_coordinator.api.async_get_alarm_state = AsyncMock(return_value="off")

    with patch("custom_components.qiara.alarm_control_panel.asyncio.sleep", AsyncMock()):
        await alarm_panel._async_confirm_state(("day", "day_armed"))

    assert alarm_panel._optimistic_state == AlarmControlPanelState.ARMED_HOME
    mock_coordinator.async_update_listeners.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_state_tolerates_poll_errors(alarm_panel, mock_coordinator):
    """Test that a transient error from a single poll attempt doesn't abort the confirm loop."""
    alarm_panel._optimistic_state = AlarmControlPanelState.DISARMED
    mock_coordinator.data = {"alarm_state": "day"}
    mock_coordinator.api.async_get_alarm_state = AsyncMock(
        side_effect=[Exception("transient"), "off"]
    )

    with patch("custom_components.qiara.alarm_control_panel.asyncio.sleep", AsyncMock()):
        await alarm_panel._async_confirm_state(("off",))

    assert mock_coordinator.data["alarm_state"] == "off"
    assert alarm_panel._optimistic_state is None
