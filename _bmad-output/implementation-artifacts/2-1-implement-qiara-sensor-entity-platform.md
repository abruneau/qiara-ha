# Story 2.1: Implement Qiara Sensor Entity Platform

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want to create the Home Assistant sensor platform for Qiara devices,
So that sensor entities can be properly registered and managed within Home Assistant.

## Acceptance Criteria

1.  **Given** the core Qiara integration (Epic 1) is functional,
2.  **When** the Qiara custom component is loaded,
3.  **Then** a `sensor.py` file is present in the `custom_components/qiara/` directory,
4.  **And** it correctly defines the setup for Qiara sensor entities according to Home Assistant guidelines.

## Tasks / Subtasks

- [x] Define `sensor.py` within `custom_components/qiara/`
- [x] Implement setup logic for Qiara sensor entities
- [x] Ensure proper registration and management of sensors within Home Assistant
- [x] Integrate with the Qiara API via the service layer to fetch sensor data
- [x] Implement error handling for sensor data retrieval
- [x] Adhere to Home Assistant's `async_client` for API calls
- [x] Implement data validation for sensor responses using Pydantic

## Dev Notes

### Relevant Architecture Patterns and Constraints
-   Conform to Home Assistant architecture and development standards for custom components.
-   Employ a Service Layer Pattern for internal API interaction structure (e.g., `custom_components/qiara/api/`).
-   Interact with the Qiara API exclusively through the `api/` Service Layer.
-   Adapt `qiara-python-sdk` to use Home Assistant's `async_client` for secure and asynchronous API calls.
-   Use Pydantic models for all sensor data validation and internal data representation of API responses.
-   Manage configuration through Home Assistant's Config Flow (established in Epic 1).
-   Ensure all custom events and services follow defined naming conventions (e.g., `DOMAIN_EVENT_TYPE`, `snake_case`).
-   Convert Pydantic model data to conform to Home Assistant entity state/attribute expectations.
-   Implement authentication using Home Assistant Config Flow.
-   Implement Exponential Backoff with Retries for Qiara API rate limiting.
-   Integrate Home Assistant's Built-in Logging for monitoring and logging of sensor operations.
-   Use Home Assistant's built-in exceptions (`UpdateFailed`, `ConfigEntryAuthFailed`) for error handling.

### Source Tree Components to Touch
-   `custom_components/qiara/sensor.py` (new file for sensor platform definition)
-   `custom_components/qiara/__init__.py` (for component setup and API service initialization)
-   `custom_components/qiara/config_flow.py` (potential updates for sensor-specific configuration, if any)
-   `custom_components/qiara/api/` (for adding methods to retrieve sensor data)
-   `custom_components/qiara/manifest.json` (to declare the sensor platform)
-   `tests/` directory (for unit and integration tests related to sensor entities).

### Testing Standards Summary
-   Unit tests are required for sensor data parsing, API interaction, and entity state updates.
-   Integration tests should cover the full lifecycle of a sensor entity from setup to state changes within Home Assistant.
-   Automated testing should be integrated into the CI/CD pipeline via GitHub Actions.
-   Adhere to Python PEP 8 standards, enforced by `black` and `ruff`.

### Project Structure Notes
-   **Alignment with unified project structure (paths, modules, naming):**
    -   Adhere to standard Home Assistant custom component directory structure (`custom_components/qiara/`).
    -   Follow Python PEP 8 style guidelines, enforced by automated tools (`black`, `ruff`).
    -   Project initialized using `integration_blueprint` Cookiecutter.
-   **Detected conflicts or variances (with rationale):** None identified at this stage.

### References
-   [Source: epics.md#Epic 2: Qiara Sensor Monitoring]
-   [Source: epics.md#Additional Requirements]
-   [Library: https://github.com/abruneau/qiara-api] (Qiara REST API wrapper)
-   [Library: https://github.com/abruneau/qiara-python-sdk] (Python SDK for Qiara API)
-   [Tool: Pydantic] (for data validation)
-   [Tool: black, ruff] (for code formatting and linting)
-   [Tool: GitHub Actions] (for CI/CD)
-   [HA Docs: Custom Components Sensor Platform] (Refer to official Home Assistant developer documentation for creating sensor entities)

## Dev Agent Record

### Agent Model Used

gemini-1.5-flash

### Debug Log References

### Completion Notes List

- Implemented sensor.py file with Qiara diagnostic sensors (battery)
- Implemented binary_sensor.py for Qiara security sensors (door, window, motion, etc.)
- Created QiaraBinarySensor and QiaraBatterySensor classes using Home Assistant standards
- Implemented proper device information with individual devices for each physical sensor
- Integrated Pydantic models for data validation in QiaraApi
- Added exponential backoff retry logic to QiaraApiClient
- Updated coordinator to use validated models and keyed data for easier access
- Fixed component initialization to only load implemented platforms
- Added unit tests for API client validation and retry logic

### File List

- custom_components/qiara/sensor.py
- custom_components/qiara/binary_sensor.py
- custom_components/qiara/api/__init__.py
- custom_components/qiara/api/client.py
- custom_components/qiara/models.py
- custom_components/qiara/__init__.py
- custom_components/qiara/coordinator.py
- custom_components/qiara/manifest.json
- custom_components/qiara/const.py
- tests/test_api_client.py
