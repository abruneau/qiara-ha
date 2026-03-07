# Story 2.2: Retrieve and Display Qiara Sensor Status

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Home Assistant user,
I want to see the real-time status of my Qiara security sensors (e.g., door/window, motion) in Home Assistant,
So that I can monitor the security of my home at a glance.

## Acceptance Criteria

1.  **Given** the Qiara custom component is configured and connected to the Qiara system,
2.  **When** I view my Home Assistant dashboard,
3.  **Then** sensor entities (e.g., `sensor.qiara_door_front`, `binary_sensor.qiara_motion_living_room`) are displayed,
4.  **And** these entities accurately reflect the current state (e.g., open/closed, detected/clear) of their corresponding physical Qiara sensors,
5.  **And** updates to sensor status from the Qiara system are reflected in Home Assistant in near real-time.
6.  **And** the sensor attributes include relevant information like battery level or last triggered time if available from the Qiara API.
7.  **And** the implementation MUST utilize the `qiara-python-sdk` (`openapi_client`) as mandated by the architecture.

## Tasks / Subtasks

- [x] **Critical Refactor: Integrate `qiara-python-sdk` (AC: #7)**
  - [x] Update `custom_components/qiara/manifest.json` to include the `openapi_client` dependency from Git.
  - [x] Refactor `custom_components/qiara/api/client.py` to use `openapi_client` instead of direct `aiohttp` requests.
  - [x] Adapt the SDK to use Home Assistant's `async_client` (via `hass.helpers.aiohttp_client.async_get_clientsession`).
- [x] Enhance `QiaraBinarySensor` with `extra_state_attributes` (AC: #6)
  - [x] Map `battery_level` from `QiaraSensorData` to attributes.
  - [x] Map `last_updated` from `QiaraSensorData` to a `last_triggered` attribute.
- [x] Ensure `QiaraBatterySensor` (diagnostic) accurately reflects the battery level (AC: #3, #6).
- [x] Verify `update_interval` in `coordinator.py` for "near real-time" updates (AC: #5).
- [x] Create unit tests for sensor and binary_sensor platforms (AC: #4, #6).
  - [x] Create `tests/custom_components/qiara/test_binary_sensor.py`.
  - [x] Create `tests/custom_components/qiara/test_sensor.py`.
  - [x] Verify attribute population and state updates.

## Dev Notes

### Relevant Architecture Patterns and Constraints
-   **Service Layer Pattern**: Ensure all API calls go through `coordinator.api`, which must now wrap the `openapi_client`.
-   **SDK Integration**: The `qiara-python-sdk` is available as `openapi_client`. It must be used for all API interactions.
-   **Pydantic Data Validation**: Continue using Pydantic models for data transformation between the SDK and HA entities.
-   **Home Assistant Best Practices**: 
    -   Use `extra_state_attributes` for entity-specific information.
    -   Adapt the external SDK to use HA's `async_get_clientsession`.

### Source Tree Components to Touch
-   `custom_components/qiara/manifest.json`: Add SDK dependency.
-   `custom_components/qiara/api/client.py`: Refactor to use SDK.
-   `custom_components/qiara/binary_sensor.py`: Add `extra_state_attributes`.
-   `custom_components/qiara/sensor.py`: Verify/enhance `QiaraBatterySensor`.
-   `custom_components/qiara/coordinator.py`: Potentially adjust `update_interval`.

### Testing Standards Summary
-   Tests must use `hass` fixture and `pytest`.
-   Mock the `openapi_client` responses in tests.

### Project Structure Notes
-   **Alignment with unified project structure (paths, modules, naming)**:
    -   Maintain clear separation between API logic (`api/`), models (`models.py`), and HA entities.
-   **Detected conflicts or variances (with rationale)**:
    -   Story 2.1 failed to use the required `qiara-python-sdk`. This story must correct this architectural violation.

### References
-   [Source: _bmad-output/planning-artifacts/epics.md#Story 2.2: Retrieve and Display Qiara Sensor Status]
-   [Source: requirements.txt] (Contains the git link for `openapi_client`)
-   [Architecture: _bmad-output/planning-artifacts/architecture.md#Technical Constraints & Dependencies]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List
- Integrated `openapi_client` SDK (Qiara Python SDK).
- Implemented `QiaraAsyncApiClient` and `AsyncRESTResponse` to adapt the synchronous SDK for asynchronous use with Home Assistant's `aiohttp` client.
- Updated `QiaraApiClient` to use SDK serialization and deserialization.
- Added `extra_state_attributes` to `QiaraBinarySensor` for battery level and last triggered time.
- Adjusted `update_interval` in `QiaraDataUpdateCoordinator` to 15 seconds.
- Created comprehensive unit tests for `sensor` and `binary_sensor` platforms with Home Assistant mocks.
- Verified that all 10 unit tests pass (including existing and new tests).

### File List
- `custom_components/qiara/manifest.json`
- `custom_components/qiara/api/client.py`
- `custom_components/qiara/binary_sensor.py`
- `custom_components/qiara/coordinator.py`
- `tests/custom_components/qiara/test_binary_sensor.py`
- `tests/custom_components/qiara/test_sensor.py`
- `tests/test_api_client.py`
- `tests/mocks/homeassistant/*` (Mock package for tests)

## Change Log
- 2026-02-21: Integrated Qiara Python SDK, added binary sensor attributes, and unit tests. Status set to review.

Status: review
