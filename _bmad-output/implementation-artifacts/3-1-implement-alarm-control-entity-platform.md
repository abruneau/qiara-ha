# Story 3.1: Implement Alarm Control Entity Platform

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want to create the Home Assistant alarm control panel platform for the Qiara security system,
So that the alarm system can be properly registered and controlled within Home Assistant.

## Acceptance Criteria

1. **Given** the core Qiara integration (Epic 1/2) is functional,
   **When** the Qiara custom component is loaded,
   **Then** an `alarm_control_panel.py` file is present in the `custom_components/qiara/` directory.

2. **And** the `alarm_control_panel.py` correctly defines `async_setup_entry` to register the `QiaraAlarmControlPanel` entity with Home Assistant via `async_add_entities`.

3. **And** `Platform.ALARM_CONTROL_PANEL` is added to the `PLATFORMS` list in `custom_components/qiara/__init__.py` so the platform is loaded automatically.

4. **And** the `QiaraAlarmControlPanel` entity correctly implements `alarm_arm_home()` (Day Mode), `alarm_arm_night()` (Night Mode), and `alarm_disarm()` service calls by delegating to the existing `coordinator.api.async_arm_system()` and `coordinator.api.async_disarm_system()` methods.

5. **And** the entity reports its state as one of: `AlarmControlPanelState.ARMED_HOME` (day), `AlarmControlPanelState.ARMED_NIGHT` (night), or `AlarmControlPanelState.DISARMED` using optimistic state tracking (state updates immediately after a successful API command).

6. **And** if an arm/disarm command fails, the error is logged and an appropriate exception is raised (using `HomeAssistantError`), leaving the displayed state unchanged.

7. **And** unit tests for the alarm control panel platform exist in `tests/custom_components/qiara/test_alarm_control_panel.py`.

## Tasks / Subtasks

- [x] Create `custom_components/qiara/alarm_control_panel.py` (AC: #1, #2, #4, #5, #6)
  - [x] Import `AlarmControlPanelEntity`, `AlarmControlPanelEntityFeature`, `AlarmControlPanelState` from `homeassistant.components.alarm_control_panel`
  - [x] Implement `async_setup_entry` to create and register a single `QiaraAlarmControlPanel` entity
  - [x] Implement `QiaraAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity)` class
  - [x] Set `_attr_supported_features` to include `ARM_HOME | ARM_NIGHT` (no `ARM_AWAY` — Qiara uses day/night modes)
  - [x] Implement `alarm_state` property returning the current optimistic state (`AlarmControlPanelState`)
  - [x] Implement `async_alarm_arm_home()` → calls `coordinator.api.async_arm_system(SYSTEM_MODE_DAY)`
  - [x] Implement `async_alarm_arm_night()` → calls `coordinator.api.async_arm_system(SYSTEM_MODE_NIGHT)`
  - [x] Implement `async_alarm_disarm()` → calls `coordinator.api.async_disarm_system()`
  - [x] Use optimistic state: update `_optimistic_state` on success and call `self.async_write_ha_state()`
  - [x] On command failure: log error and raise `HomeAssistantError`
- [x] Register platform in `custom_components/qiara/__init__.py` (AC: #3)
  - [x] Add `Platform.ALARM_CONTROL_PANEL` to `PLATFORMS` list
- [x] Create unit tests (AC: #7)
  - [x] Create `tests/custom_components/qiara/test_alarm_control_panel.py`
  - [x] Test `async_setup_entry` creates the entity
  - [x] Test `alarm_state` returns `DISARMED` as initial state
  - [x] Test `async_alarm_arm_home()` calls `async_arm_system("day")` and updates state
  - [x] Test `async_alarm_arm_night()` calls `async_arm_system("night")` and updates state
  - [x] Test `async_alarm_disarm()` calls `async_disarm_system()` and updates state
  - [x] Test error handling when API call fails

## Dev Notes

### Relevant Architecture Patterns and Constraints

- **Service Layer Pattern**: Arm/disarm commands MUST go through `coordinator.api.async_arm_system()` / `coordinator.api.async_disarm_system()` — NEVER call `QiaraApiClient` directly from the entity.
- **CoordinatorEntity**: Extend `CoordinatorEntity` (from `homeassistant.helpers.update_coordinator`) as done in `binary_sensor.py` and `sensor.py`.
- **Optimistic State**: The Qiara API has no real-time push for alarm status. Use optimistic state: store current state in `self._optimistic_state` (default `AlarmControlPanelState.DISARMED`), update after successful API command, call `self.async_write_ha_state()`.
- **No Code Required**: The API methods `async_arm_system(mode)` and `async_disarm_system()` ALREADY exist in `custom_components/qiara/api/__init__.py` and `api/client.py`. Do NOT reimplement them.
- **Naming Conventions**: Follow `snake_case` for methods/variables, `CamelCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **Error Handling**: Use `HomeAssistantError` for user-visible errors (from `homeassistant.exceptions`).
- **Logging**: Use `_LOGGER = logging.getLogger(__name__)` pattern.

### Source Tree Components to Touch

- **CREATE**: `custom_components/qiara/alarm_control_panel.py` (new file)
- **MODIFY**: `custom_components/qiara/__init__.py` — add `Platform.ALARM_CONTROL_PANEL` to `PLATFORMS` list (line 19-22)
- **CREATE**: `tests/custom_components/qiara/test_alarm_control_panel.py` (new test file)

### Existing Code to Reuse (Do NOT Reinvent)

| What | Where | How to Use |
|------|-------|------------|
| `async_arm_system(mode)` | `custom_components/qiara/api/__init__.py:59` | Call via `self.coordinator.api.async_arm_system(SYSTEM_MODE_DAY)` |
| `async_disarm_system()` | `custom_components/qiara/api/__init__.py:68` | Call via `self.coordinator.api.async_disarm_system()` |
| `SYSTEM_MODE_DAY`, `SYSTEM_MODE_NIGHT` | `custom_components/qiara/const.py:20-22` | Import and use for mode strings |
| `QiaraDataUpdateCoordinator` | `custom_components/qiara/coordinator.py` | Pass as first arg to `CoordinatorEntity.__init__` |
| `DOMAIN` | `custom_components/qiara/const.py:3` | For `unique_id`, `device_info` |

### HA Alarm Control Panel API Reference

```python
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)

# AlarmControlPanelEntityFeature flags:
# AlarmControlPanelEntityFeature.ARM_HOME    → alarm_arm_home()
# AlarmControlPanelEntityFeature.ARM_NIGHT   → alarm_arm_night()
# AlarmControlPanelEntityFeature.ARM_AWAY    → alarm_arm_away()  (NOT needed for Qiara)
# AlarmControlPanelEntityFeature.TRIGGER     → alarm_trigger()   (NOT needed here)

# AlarmControlPanelState enum values:
# AlarmControlPanelState.DISARMED
# AlarmControlPanelState.ARMED_HOME   ← maps to Qiara "day" mode
# AlarmControlPanelState.ARMED_NIGHT  ← maps to Qiara "night" mode
# AlarmControlPanelState.ARMING
# AlarmControlPanelState.TRIGGERED
```

### Testing Standards Summary

- Tests use `pytest` with `hass` fixture pattern (as in `tests/custom_components/qiara/test_binary_sensor.py`)
- Mock `coordinator.api.async_arm_system` and `coordinator.api.async_disarm_system` using `MagicMock` / `AsyncMock`
- Mock the coordinator `data` dict with sample `QiaraSensorData` objects if needed
- See existing test files for mock patterns: `tests/custom_components/qiara/test_binary_sensor.py`

### Project Structure Notes

- **Alignment**: New files follow the existing platform pattern (`sensor.py`, `binary_sensor.py` → `alarm_control_panel.py`)
- **Test directory**: Tests go in `tests/custom_components/qiara/` (not `tests/` root)
- **No conflicts detected**: This story introduces a new platform with no breaking changes to existing platforms

### Previous Story Intelligence (from Story 2.2)

From the Story 2.2 completion notes, key patterns established:
- Authentication uses HMAC-SHA1 challenge/response stored in `_session_id`; `x-hlcore-session-id` header used (not Bearer token) — arm/disarm already correctly uses this header
- `CoordinatorEntity` pattern works: entities get data from `coordinator.data` dict
- Tests mock the HA `hass` object; `coordinator.api` is the entry point for all API calls
- `_LOGGER` at module level, all debug/warning/error logged before raising exceptions

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#API & Communication Patterns]
- [Source: custom_components/qiara/api/__init__.py#async_arm_system / async_disarm_system]
- [Source: custom_components/qiara/api/client.py#async_arm_system / async_disarm_system]
- [Source: custom_components/qiara/const.py#SYSTEM_MODE_DAY/NIGHT/DISARMED]
- [Source: custom_components/qiara/__init__.py#PLATFORMS]
- [Source: custom_components/qiara/binary_sensor.py] (pattern reference for CoordinatorEntity)
- [HA Docs: homeassistant.components.alarm_control_panel.AlarmControlPanelEntity]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Created `alarm_control_panel.py` with `QiaraAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity)`.
- Supported features: `ARM_HOME | ARM_NIGHT` (Qiara day/night modes). `_attr_code_arm_required = False` to suppress HA PIN UI.
- Optimistic state pattern used: `_optimistic_state` updated on successful API command, `async_write_ha_state()` called after.
- All arm/disarm commands delegate to `coordinator.api.async_arm_system()` / `async_disarm_system()` via service layer.
- `HomeAssistantError` raised on API failure; no entity-level logging (API layer already handles it).
- Added `Platform.ALARM_CONTROL_PANEL` to `PLATFORMS` in `__init__.py`.
- Created mock for `homeassistant.components.alarm_control_panel` in `tests/mocks/`.
- 10 unit tests cover: init, initial state, supported features, arm home/night (with `async_write_ha_state` assertion), disarm (with `async_write_ha_state` assertion), error cases (×3 — disarm error verifies armed state preserved), availability.
- All 21 tests pass (10 new + 11 existing) — zero regressions.

### File List

- `custom_components/qiara/alarm_control_panel.py` (created)
- `custom_components/qiara/__init__.py` (modified — added `Platform.ALARM_CONTROL_PANEL` to `PLATFORMS`)
- `tests/custom_components/qiara/test_alarm_control_panel.py` (created)
- `tests/mocks/homeassistant/components/alarm_control_panel/__init__.py` (created)
- `tests/mocks/homeassistant/helpers/entity/__init__.py` (modified — added `DeviceInfo` mock class)

## Change Log

- 2026-03-15: Implemented alarm control panel platform. Created `alarm_control_panel.py` with optimistic state, arm home/night, disarm, error handling. Registered platform in `__init__.py`. Added 10 unit tests. All 21 tests pass. Status set to review.
- 2026-03-15: Code review fixes — removed double-logging from error handlers (API layer already logs); added `_attr_code_arm_required = False` to suppress spurious PIN UI; strengthened `test_alarm_disarm_error` to verify armed state is preserved on failure; added `async_write_ha_state()` call assertions to arm/disarm success tests. All 21 tests pass. Status set to done.
- 2026-03-17: Adversarial code review fixes — H1: removed error message double-wrapping (entity now uses `str(err)` instead of adding a prefix, so the API's message passes through clean); M1/M2: added 2 tests (`test_alarm_arm_home_update_failed_not_double_wrapped`, `test_alarm_arm_home_node_not_yet_discovered`) to guard the real UpdateFailed→HomeAssistantError chain and the alarm-node-not-discovered path; M3: replaced plain dict `_attr_device_info` with `DeviceInfo(...)` and added `DeviceInfo` mock to entity mock. All 23 tests pass. Status: done.
