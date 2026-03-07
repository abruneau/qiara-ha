---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['prd/home-assistant-qiara-plugin-prd.md']
workflowType: 'architecture'
project_name: 'qiara-ha'
user_name: 'Antonin'
date: 'Monday, February 9, 2026'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
The core functional requirements involve integrating Qiara security system functionalities into Home Assistant. Architecturally, this means designing modules to:
- Ingest and display real-time sensor status updates.
- Send commands to arm/disarm the Qiara system, requiring a robust command dispatch mechanism.
- Stream live video, necessitating efficient data handling and potentially transcoding.
- Trigger Home Assistant notifications, implying a reliable event-driven notification system.
- Provide a self-contained local development environment, which points to a need for clear dependency management and containerization strategies.

**Non-Functional Requirements:**
The architecture must prioritize:
- **API Integration:** Seamless and efficient utilization of `qiara-api` and `qiara-python-sdk`. This implies understanding their rate limits, authentication mechanisms, and data structures.
- **Home Assistant Best Practices:** Adherence to HA component development guidelines for stability, future compatibility, and ease of maintenance. This affects module structure, entity creation, and service definitions.
- **Security:** Secure authentication with the Qiara system is paramount, requiring careful consideration of token management, credential storage, and secure communication protocols.
- **Reliability and Error Handling:** Robust error handling and logging are critical, especially for a security system. The architecture should include mechanisms for graceful degradation, retry logic, and clear diagnostic reporting.

**Scale & Complexity:**
This project is assessed as having **medium complexity**.

- Primary domain: Integration, IoT (Home Automation), API Development. This solution bridges hardware (Qiara), external APIs, and a home automation platform (Home Assistant).
- Complexity level: Medium. The real-time aspects (video, notifications) combined with secure multi-system integration elevate it beyond simple automation.
- Estimated architectural components: (This will be determined in subsequent steps, but at this stage, we can infer components like API clients, data parsers, HA entities, notification handlers, and potentially a video stream processor.)

### Technical Constraints & Dependencies

- **Existing Libraries:** The project is constrained by and dependent on `https://github.com/abruneau/qiara-api` and `https://github.com/abruneau/qiara-python-sdk`. Architectural decisions will need to align with the capabilities and limitations of these libraries.
- **Home Assistant Platform:** Development must conform to the Home Assistant architecture and development standards, influencing component design and data flow.

### Cross-Cutting Concerns Identified

- **Authentication/Authorization:** Critical for secure interaction between Home Assistant and the Qiara system.
- **State Management:** Maintaining a consistent view of the Qiara system's state within Home Assistant (e.g., armed/disarmed status, sensor states).
- **Reliability:** Ensuring continuous operation and accurate reporting, especially for security-critical functions and notifications.
- **Performance:** Optimizing for low latency, particularly for video streaming and rapid notification delivery.
- **Maintainability:** Designing for ease of updates, debugging, and extension in the Home Assistant ecosystem.

## Starter Template Evaluation

### Primary Technology Domain

Home Assistant Custom Component (Python), adhering to Python plugin development best practices.

### Starter Options Considered

- **Official Home Assistant Scaffold Script:** A basic starting point.
- **`integration_blueprint` by Ludeeus (and its Cookiecutter variant):** A comprehensive, community-recommended template with HACS support, dev containers, and pre-configured quality tools.

### Selected Starter: `integration_blueprint` (via Cookiecutter)

**Rationale for Selection:**
This starter is selected to ensure adherence to Home Assistant development best practices from the outset. It provides a robust, well-structured, and maintainable foundation that includes critical features for a production-quality integration:

- **HACS Compatibility:** Designed for easy distribution via the Home Assistant Community Store.
- **Reproducible Dev Environment:** Utilizes VS Code Dev Containers for a consistent and isolated development setup.
- **Code Quality:** Pre-configured with `pytest`, `black`, and `ruff` to enforce testing, formatting, and linting standards.
- **Community Backing:** Actively maintained and widely used within the Home Assistant community.

**Initialization Command:**

```bash
cookiecutter gh:oncleben31/cookiecutter-homeassistant-custom-component
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Python with type hinting.

**Styling Solution:**
- Not applicable for a backend integration.

**Build Tooling:**
- Standard Python packaging and dependency management.

**Testing Framework:**
- `pytest` for unit and integration testing.

**Code Organization:**
- Adherence to Home Assistant custom component conventions (`__init__.py`, `manifest.json`, `config_flow.py`, `sensor.py`, etc.).
- Clear separation of configuration flow from component logic.
- Modular structure by platform (e.g., `sensor`, `switch`).

**Development Experience:**
- Optimized for debugging within the VS Code Dev Container environment.
- Pre-configured testing infrastructure.
- Supports HACS-friendly documentation.

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
*   **Authentication Method:** Home Assistant Config Flow.
*   **API Security Strategy:** Adapt `qiara-python-sdk` to use Home Assistant's `async_client`.
*   **CI/CD Pipeline:** GitHub Actions.

**Important Decisions (Shape Architecture):**
*   **Data Validation Strategy:** Pydantic.
*   **API Design Patterns:** Service Layer Pattern.
*   **Error Handling Standards:** Utilize Home Assistant's built-in exceptions (`UpdateFailed`, `ConfigEntryAuthFailed`).
*   **Rate Limiting Strategy:** Exponential Backoff with Retries.
*   **Monitoring and Logging Strategy:** Home Assistant's Built-in Logging.

**Deferred Decisions (Post-MVP):**
*   Caching Strategy for API Calls: No caching (chosen for simplicity, but could be revisited if performance or rate limits become an issue).

### Data Architecture

*   **Caching Strategy for API calls:** No Caching.
    *   *Rationale:* User preference for implementation simplicity, accepting the implications of potential performance impact and higher risk of hitting API rate limits.
*   **Data Validation Strategy:** Pydantic.
    *   *Rationale:* Provides robust and declarative data validation, improving reliability and reducing boilerplate, crucial for a security system integration.

### Authentication & Security

*   **Authentication method (how to store and refresh Qiara API tokens):** Home Assistant Config Flow.
    *   *Rationale:* Aligns with Home Assistant best practices for secure credential management, offers secure storage, and allows for robust token refresh logic, enhancing user experience and security.
*   **API security strategy (protecting credentials within HA):** Adapt `qiara-python-sdk` to use Home Assistant's `async_client`.
    *   *Rationale:* Ensures consistent and secure HTTP request handling within the Home Assistant ecosystem, integrates seamlessly with Config Flow's token management, and adheres to HA best practices.

### API & Communication Patterns

*   **API design patterns (how the HA integration will be structured internally to interact with the `qiara-python-sdk`):** Service Layer Pattern.
    *   *Rationale:* Provides clear separation of concerns, enhances maintainability, and allows for centralized handling of interactions with the `qiara-python-sdk` and HA-specific data transformations.
*   **Error handling standards (specific retry logic, user-facing error messages):** Utilize Home Assistant's built-in exceptions (`UpdateFailed`, `ConfigEntryAuthFailed`).
    *   *Rationale:* Ensures consistency with the HA ecosystem, provides standardized user feedback, and allows HA to handle retry mechanisms where appropriate.
*   **Rate limiting strategy (how to handle API rate limits from Qiara):** Exponential Backoff with Retries.
    *   *Rationale:* Provides a robust and automatic way to handle temporary rate limits, crucial for maintaining the reliability of a security system integration.

### Infrastructure & Deployment

*   **CI/CD pipeline approach (how to automate testing and releases, possibly to HACS):** GitHub Actions.
    *   *Rationale:* Provides robust workflows for testing, linting, and release automation, naturally fitting a GitHub-hosted, HACS-compatible Home Assistant custom component.
*   **Monitoring and logging strategy (how to provide useful logs for debugging):** Home Assistant's Built-in Logging.
    *   *Rationale:* Standard and expected way to log within HA, providing a consistent experience for users and integrating with HA's diagnostic tools.

### Decision Impact Analysis

**Implementation Sequence:**
1.  **Starter Template Initialization:** Use `cookiecutter gh:oncleben31/cookiecutter-homeassistant-custom-component`.
2.  **Home Assistant Config Flow Implementation:** Set up the initial configuration flow for authentication.
3.  **`qiara-python-sdk` Adaptation:** Modify the SDK to use HA's `async_client`.
4.  **Service Layer Implementation:** Develop the service layer to interact with the adapted SDK.
5.  **Pydantic Data Validation:** Integrate Pydantic for robust data validation.
6.  **Error Handling Integration:** Implement Home Assistant's built-in exceptions for error handling.
7.  **Rate Limiting with Exponential Backoff:** Implement the retry mechanism for API calls.
8.  **GitHub Actions CI/CD Setup:** Configure the CI/CD pipeline for testing and releases.
9.  **Home Assistant Built-in Logging:** Integrate HA's logging system.

**Cross-Component Dependencies:**
*   The **Home Assistant Config Flow** provides credentials to the **Service Layer** which uses the **adapted `qiara-python-sdk`**.
*   **Pydantic** is used within the **Service Layer** for data validation of responses from the `qiara-python-sdk`.
*   **Error Handling** and **Rate Limiting** are managed within the **Service Layer** and propagate to Home Assistant via its exceptions.
*   **GitHub Actions** automates testing of all components and prepares for deployment into a Home Assistant instance.
*   **Home Assistant Built-in Logging** will be utilized across all components for debugging and monitoring.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
5 areas where AI agents could make different choices (Naming, Structural, Format, Communication, Process).

### Naming Patterns

**Code Naming Conventions:**
1.  **Python Modules/Files:** `snake_case` (e.g., `sensor.py`, `my_helper.py`).
2.  **Python Classes:** `CamelCase` (e.g., `QiaraDevice`, `SensorEntity`).
3.  **Python Functions/Methods:** `snake_case` (e.g., `async_setup_entry`, `get_device_status`).
4.  **Python Variables:** `snake_case` (e.g., `device_id`, `temperature_value`).
5.  **Python Constants:** `UPPER_SNAKE_CASE` (e.g., `DOMAIN`, `CONF_API_KEY`).
6.  **Home Assistant Entity IDs:** `snake_case` for the suffix after the platform prefix (e.g., `sensor.qiara_hub_temperature`).
7.  **Home Assistant Service Names:** `snake_case` for custom services (e.g., `qiara.arm_away`).

### Structure Patterns

**Project Organization:**
1.  **Tests:** Top-level `tests/` directory (`tests/components/qiara/`).
2.  **Within `custom_components/qiara/`:**
    *   Standard HA platform files (e.g., `sensor.py`, `switch.py`).
    *   `const.py`, `config_flow.py`, `__init__.py`, `manifest.json`, `services.yaml`, `translations/`.
    *   **New directories:** `models/` (for Pydantic), `api/` (for Service Layer), and `helpers/` or `util/` (for reusable utilities).

### Format Patterns

**API Response Formats:**
1.  **Internal Representation:** Pydantic model instances for validated data.
2.  **Conversion to HA Entities:** Ensure data types and formats conform to Home Assistant's expectations.

**Data Exchange Formats:**
1.  **JSON Field Naming:** `snake_case` for JSON fields.
2.  **Date/Time Formats:** **ISO 8601 (UTC)** for all date and time information.
3.  **Boolean Representations:** Standard Python `True`/`False`.

### Communication Patterns

**Event System Patterns:**
1.  **HA Event Bus:** Utilize `hass.bus.async_fire` for custom events.
2.  **Event Naming Convention:** `DOMAIN_EVENT_TYPE` (e.g., `qiara_security.alarm_triggered`).
3.  **Event Payload Structure:** JSON-serializable dictionaries, potentially using Pydantic models.

**State Management Patterns:**
1.  **HA Entity State:** Primary source of truth for device state.
2.  **`DataUpdateCoordinator`:** For regularly polling the Qiara API and updating entities.
3.  **Immutable State Updates:** Strive for immutable updates.

### Process Patterns

**Error Handling Patterns:**
1.  **Centralized Error Handling:** Transform errors into appropriate Home Assistant exceptions.
2.  **Specific Error Mapping:** Map known Qiara API errors to user-friendly HA messages.
3.  **Automatic Retry for Transient Errors:** Apply Exponential Backoff with Retries.

**Loading State Patterns:**
1.  **`DataUpdateCoordinator` Loading States:** Leverage `DataUpdateCoordinator` to manage entity loading states.
2.  **Clear User Feedback:** Provide clear status messages in Home Assistant's UI.

### Enforcement Guidelines

**All AI Agents MUST:**

-   Adhere to Python PEP 8 standards, enforced by `black` and `ruff`.
-   Utilize Pydantic models for all data validation and internal data representation of API responses.
-   Interact with the Qiara API exclusively through the `api/` Service Layer.
-   Manage configuration through Home Assistant's Config Flow.
-   Utilize Home Assistant's built-in logging mechanisms.
-   Handle transient errors and rate limits with Exponential Backoff and Retries.
-   Ensure all custom events and services follow the defined naming conventions.
-   Convert Pydantic model data to conform to Home Assistant entity state/attribute expectations.

**Pattern Enforcement:**
-   Automated CI checks (GitHub Actions) for linting, formatting, and unit tests.
-   Code reviews to ensure adherence to architectural patterns and Home Assistant best practices.
-   Documentation of these patterns in the `architecture.md` to serve as a single source of truth.

### Pattern Examples

**Good Examples:**
```python
# Code Naming
# custom_components/qiara/sensor.py
# custom_components/qiara/helpers/time_utils.py

class QiaraDevice: # CamelCase
    def __init__(self, device_id: str): # snake_case
        self.device_id = device_id # snake_case

DOMAIN = "qiara" # UPPER_SNAKE_CASE

# Home Assistant Entity ID
# sensor.qiara_motion_sensor_front_door

# Event Naming
# hass.bus.async_fire("qiara_security.alarm_triggered", {"trigger_type": "motion"})

# Error Handling
# raise UpdateFailed("Failed to fetch device status from Qiara API")
```

**Anti-Patterns:**
```python
# Inconsistent Naming
# class qiaradevice: (should be CamelCase)
# MY_VARIABLE = "value" (should be snake_case for variables)
# sensor.qiaraMotionSensorFrontDoor (HA entity ID should be snake_case)

# Direct API Calls outside Service Layer
# Avoid direct calls to qiara_python_sdk.get_status() from entity platforms.
# Instead, call self.coordinator.qiara_api.get_status() or similar.

# Inconsistent Error Handling
# try:
#   # api call
# except Exception as e:
#   _LOGGER.error(f"Generic error: {e}") # Should map to HA exceptions
```