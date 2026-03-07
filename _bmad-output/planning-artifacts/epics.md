---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - prd/home-assistant-qiara-plugin-prd.md
  - _bmad-output/planning-artifacts/architecture.md
---

# qiara-ha - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for qiara-ha, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Display the current state (e.g., open/closed, motion detected/clear) of all configured Qiara sensors (door/window sensors, motion sensors, etc.) within Home Assistant.
FR2: Ability to arm the Qiara security system in "Day Mode" from Home Assistant.
FR3: Ability to arm the Qiara security system in "Night Mode" from Home Assistant.
FR4: Ability to disarm the Qiara security system from Home Assistant.
FR5: Integrate live video streams from Qiara security cameras into Home Assistant's dashboard.
FR6: Trigger Home Assistant notifications (e.g., persistent notifications, mobile app notifications) when the Qiara alarm system is activated.
FR7: Provide a `docker-compose.yaml` setup to facilitate local development and testing of the Home Assistant Qiara plugin, including necessary dependencies and a pre-configured Home Assistant instance.

### NonFunctional Requirements

NFR1: Adhere to Home Assistant's best practices and API guidelines for component development.
NFR2: Securely handle authentication with the Qiara security system.
NFR3: Implement robust error handling and logging for reliable operation.

### Additional Requirements

- Leverage `https://github.com/abruneau/qiara-api` and `https://github.com/abruneau/qiara-python-sdk` libraries.
- Conform to Home Assistant architecture and development standards.
- Use `integration_blueprint` via Cookiecutter (`cookiecutter gh:oncleben31/cookiecutter-homeassistant-custom-component`) for project initialization.
- Implement authentication using Home Assistant Config Flow.
- Adapt `qiara-python-sdk` to use Home Assistant's `async_client` for API security.
- Utilize GitHub Actions for CI/CD pipeline.
- Implement data validation using Pydantic.
- Employ a Service Layer Pattern for internal API interaction structure.
- Use Home Assistant's built-in exceptions (`UpdateFailed`, `ConfigEntryAuthFailed`) for error handling.
- Implement Exponential Backoff with Retries for API rate limiting.
- Integrate Home Assistant's Built-in Logging for monitoring and logging.
- Adhere to Python PEP 8 standards, enforced by `black` and `ruff`.
- Use Pydantic models for all data validation and internal data representation of API responses.
- Interact with the Qiara API exclusively through the `api/` Service Layer.
- Manage configuration through Home Assistant's Config Flow.
- Ensure all custom events and services follow the defined naming conventions (e.g., `DOMAIN_EVENT_TYPE`, `snake_case` for service names).
- Convert Pydantic model data to conform to Home Assistant entity state/attribute expectations.
- No additional requirements from UX as no UX document was found.

### FR Coverage Map

FR1: Epic 2 - Qiara Sensor Monitoring
FR2: Epic 3 - Qiara Alarm System Control
FR3: Epic 3 - Qiara Alarm System Control
FR4: Epic 3 - Qiara Alarm System Control
FR5: Epic 4 - Qiara Live Video Streaming
FR6: Epic 5 - Qiara Alarm Notifications
FR7: Epic 1 - Plugin Initialization and Core Framework

## Epic List

### Epic 1: Plugin Initialization and Core Framework
Users can install the Qiara Home Assistant plugin, securely configure it, and have the basic framework for reliable communication with the Qiara system and adhere to HA development standards.
**FRs covered:** FR7, and all "Additional Requirements" (initial setup, authentication, architecture patterns, CI/CD, coding standards, data validation, error handling, rate limiting, logging, etc.).### Epic 2: Qiara Sensor Monitoring
Users can monitor the real-time status (e.g., open/closed, motion detected/clear) of their Qiara security sensors directly within Home Assistant.
**FRs covered:** FR1

### Story 2.1: Implement Qiara Sensor Entity Platform
As a developer,
I want to create the Home Assistant sensor platform for Qiara devices,
So that sensor entities can be properly registered and managed within Home Assistant.

**Acceptance Criteria:**

**Given** the core Qiara integration (Epic 1) is functional,
**When** the Qiara custom component is loaded,
**Then** a `sensor.py` file is present in the `custom_components/qiara/` directory,
**And** it correctly defines the setup for Qiara sensor entities according to Home Assistant guidelines.

### Story 2.2: Retrieve and Display Qiara Sensor Status
As a Home Assistant user,
I want to see the real-time status of my Qiara security sensors (e.g., door/window, motion) in Home Assistant,
So that I can monitor the security of my home at a glance.

**Acceptance Criteria:**

**Given** the Qiara custom component is configured and connected to the Qiara system,
**When** I view my Home Assistant dashboard,
**Then** sensor entities (e.g., `sensor.qiara_door_front`, `binary_sensor.qiara_motion_living_room`) are displayed,
**And** these entities accurately reflect the current state (e.g., open/closed, detected/clear) of their corresponding physical Qiara sensors,
**And** updates to sensor status from the Qiara system are reflected in Home Assistant in near real-time.
**And** the sensor attributes include relevant information like battery level or last triggered time if available from the Qiara API.
### Epic 3: Qiara Alarm System Control
Users can conveniently arm and disarm their Qiara security system in various modes (Day, Night, Disarm) from Home Assistant.
**FRs covered:** FR2, FR3, FR4

### Story 3.1: Implement Alarm Control Entity Platform
As a developer,
I want to create the Home Assistant alarm control platform for the Qiara security system,
So that the alarm system can be properly registered and controlled within Home Assistant.

**Acceptance Criteria:**

**Given** the core Qiara integration (Epic 1) is functional,
**When** the Qiara custom component is loaded,
**Then** an `alarm_control_panel.py` file is present in the `custom_components/qiara/` directory,
**And** it correctly defines the setup for the Qiara alarm control entity according to Home Assistant guidelines.

### Story 3.2: Arm Qiara System in Day Mode
As a Home Assistant user,
I want to arm my Qiara security system in "Day Mode" from Home Assistant,
So that my home is secured with specific sensor configurations for daytime activity.

**Acceptance Criteria:**

**Given** the Qiara alarm control panel is displayed in Home Assistant,
**When** I select "Arm Day" for the Qiara alarm control panel,
**Then** the Qiara security system is successfully armed in Day Mode,
**And** the state of the alarm control panel in Home Assistant reflects "armed_day".
**And** if the command fails, an appropriate error message is displayed.

### Story 3.3: Arm Qiara System in Night Mode
As a Home Assistant user,
I want to arm my Qiara security system in "Night Mode" from Home Assistant,
So that my home is secured with specific sensor configurations for nighttime.

**Acceptance Criteria:**

**Given** the Qiara alarm control panel is displayed in Home Assistant,
**When** I select "Arm Night" for the Qiara alarm control panel,
**Then** the Qiara security system is successfully armed in Night Mode,
**And** the state of the alarm control panel in Home Assistant reflects "armed_night".
**And** if the command fails, an appropriate error message is displayed.

### Story 3.4: Disarm Qiara System
As a Home Assistant user,
I want to disarm my Qiara security system from Home Assistant,
So that I can freely move around my home without triggering the alarm.

**Acceptance Criteria:**

**Given** the Qiara alarm control panel is displayed in Home Assistant,
**When** I select "Disarm" for the Qiara alarm control panel and provide the correct disarm code (if required by Qiara),
**Then** the Qiara security system is successfully disarmed,
**And** the state of the alarm control panel in Home Assistant reflects "disarmed".
**And** if the command fails or the code is incorrect, an appropriate error message is displayed.
### Epic 4: Qiara Live Video Streaming
Users can view live video feeds from their Qiara security cameras within their Home Assistant dashboard, enabling visual monitoring.
**FRs covered:** FR5

### Story 4.1: Implement Camera Entity Platform
As a developer,
I want to create the Home Assistant camera platform for Qiara devices,
So that camera entities can be properly registered and managed within Home Assistant.

**Acceptance Criteria:**

**Given** the core Qiara integration (Epic 1) is functional,
**When** the Qiara custom component is loaded,
**Then** a `camera.py` file is present in the `custom_components/qiara/` directory,
**And** it correctly defines the setup for Qiara camera entities according to Home Assistant guidelines.

### Story 4.2: Stream Live Video from Qiara Cameras
As a Home Assistant user,
I want to view live video feeds from my Qiara security cameras directly within Home Assistant,
So that I can visually monitor activities in and around my home.

**Acceptance Criteria:**

**Given** the Qiara custom component is configured and connected to the Qiara system,
**When** I access a Qiara camera entity in Home Assistant,
**Then** a live video stream from the corresponding Qiara camera is displayed in the Home Assistant dashboard,
**And** the video stream is relatively low latency and stable,
**And** if the stream is unavailable, an appropriate message or placeholder is displayed.
### Epic 5: Qiara Alarm Notifications
Users receive immediate and informative notifications within Home Assistant when their Qiara security system alarm is triggered, allowing for prompt action.
**FRs covered:** FR6

### Story 5.1: Implement Alarm Trigger Notification Event
As a developer,
I want to configure the Qiara custom component to fire a Home Assistant event when the Qiara alarm system is triggered,
So that other Home Assistant automations and scripts can react to alarm events.

**Acceptance Criteria:**

**Given** the Qiara custom component is running and connected to the Qiara system,
**When** the Qiara alarm system is triggered (e.g., by a sensor),
**Then** a Home Assistant event (e.g., `qiara_security.alarm_triggered`) is fired,
**And** the event payload includes relevant information about the alarm trigger (e.g., timestamp, triggering sensor ID).

### Story 5.2: Display Persistent Notification for Alarm Trigger
As a Home Assistant user,
I want to receive a persistent notification in Home Assistant when the Qiara alarm system is triggered,
So that I am immediately aware of an active alarm.

**Acceptance Criteria:**

**Given** the Qiara custom component is configured and an alarm event is fired,
**When** the Qiara alarm system is triggered,
**Then** a new persistent notification appears in the Home Assistant UI,
**And** the notification message clearly indicates that the Qiara alarm has been triggered.

### Story 5.3: Send Mobile App Notification for Alarm Trigger
As a Home Assistant user,
I want to receive a mobile app notification on my connected devices when the Qiara alarm system is triggered,
So that I am alerted even when I am not actively viewing the Home Assistant dashboard.

**Acceptance Criteria:**

**Given** the Home Assistant mobile app is configured on my device and the Qiara custom component is running,
**When** the Qiara alarm system is triggered,
**Then** a push notification is sent to my connected Home Assistant mobile app(s),
**And** the notification message clearly indicates that the Qiara alarm has been triggered.


