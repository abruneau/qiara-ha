# Qiara integration — code review

Reviewed at commit `575fe32` (v0.1.1) against the Home Assistant
[integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
and current core patterns.

Findings marked **[verified]** were reproduced by executing the code in this repo, not just read.

---

## Contents

- [Security](#security)
- [Correctness](#correctness)
- [Type mapping](#type-mapping)
- [Quality scale gaps](#quality-scale-gaps)
- [Housekeeping](#housekeeping)
- [Suggested order of work](#suggested-order-of-work)

---

## Security

### S1 — The camera stream proxy is unauthenticated and relays to the whole device API
`camera.py:47-112`

The view sets `requires_auth = False`, `cors_allowed = True`, and returns
`Access-Control-Allow-Origin: *`. It then interpolates the `{quality}` and `{file}` path
variables straight into the upstream URL:

```python
tail = f"{quality}/{file}" if quality else file
upstream_url = f"{self._device_base_url}/home/stream/{tail}"
```

aiohttp percent-decodes path variables before handing them to the handler, and `yarl`
normalises `../` when the URL is built — so the `/home/stream/` prefix is escapable.
**[verified]** end-to-end against a live aiohttp router:

| Request to HA | Upstream URL actually fetched |
|---|---|
| `/api/qiara/camera/7/stream/HLS.m3u8` | `https://device/api/v1/home/stream/HLS.m3u8` |
| `/api/qiara/camera/7/stream/..%2F..%2Flogin%2Fchallenge` | `https://device/api/v1/login/challenge` |
| `/api/qiara/camera/7/stream/..%2F..%2Fhome%2Fnodes` | `https://device/api/v1/home/nodes` |

The proxy injects a valid `x-hlcore-session-id` on every one of those. So an unauthenticated
caller reaches arbitrary GET endpoints on the alarm device with the integration's own
authenticated session. Separately, *any* GET to this view calls `async_activate_camera`, so an
unauthenticated caller can open the camera shutter and watch the stream.

Fix:

- Leave `requires_auth` at its default `True`; HA's `stream` component authenticates its own
  fetches. If ffmpeg genuinely cannot carry the auth header, use
  `homeassistant.components.http.async_sign_path` to mint a short-lived signed URL instead of
  opening the endpoint.
- Validate the path components before building the upstream URL:
  ```python
  _SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
  if not _SEGMENT_RE.match(file) or (quality and not _SEGMENT_RE.match(quality)):
      return web.Response(status=400)
  ```
  (`.` is allowed but `..` is rejected by also checking `".." not in (file, quality)`.)
- Drop `cors_allowed` and the wildcard `Access-Control-Allow-Origin` unless a specific
  cross-origin consumer needs them.

### S2 — TLS verification is disabled unconditionally, including against the cloud API
`api/client.py:114`

```python
config = Configuration(host=self._base_url)
config.verify_ssl = False
```

`call_api_async` passes `ssl=self.configuration.verify_ssl`, so *every* request runs with
verification off — including `POST /login/new`, which carries the HMAC challenge response. The
default base URL is `https://api.qiara.co/api/v1`, a **cloud** endpoint, where a MITM can lift
the session ID and then arm/disarm the alarm. `camera.py:78` does the same with
`async_get_clientsession(hass, verify_ssl=False)`.

Fix: default to verification on, and expose "device uses a self-signed certificate" as an
explicit checkbox in the config flow that only applies to non-public hosts.

---

## Correctness

### H1 — The alarm panel sticks in its optimistic state forever when confirmation times out
`alarm_control_panel.py:96-101`, `164-184`

`alarm_state` short-circuits on `_optimistic_state`, and the docstring says it "is cleared once
`_async_confirm_state` verifies the device agrees". On the timeout path it is *not* cleared, and
there is no `_handle_coordinator_update` override to clear it later — so the log message
"keeping optimistic state until next sync" describes behaviour that does not exist.

**[verified]**: after a command whose confirmation never matches, the panel reports
`ARMED_HOME` permanently while the coordinator holds `"off"`. Disarming at the physical keypad
leaves HA showing "Armed home" indefinitely, and no subsequent poll or push event can recover it.

Fix — clear the override whenever fresh coordinator data arrives:

```python
@callback
def _handle_coordinator_update(self) -> None:
    """Coordinator data is authoritative once it arrives."""
    self._optimistic_state = None
    super()._handle_coordinator_update()
```

and have `_async_confirm_state` clear it on timeout too, so the panel falls back to the device's
truth rather than a guess.

### H2 — An unknown or unreadable alarm state renders as "Disarmed"
`alarm_control_panel.py:98-101`, `api/__init__.py:209-228`

`async_get_alarm_state` catches every exception and returns `None`. The panel then does:

```python
return _ALARM_STATE_MAP.get(raw, AlarmControlPanelState.DISARMED)
...
return AlarmControlPanelState.DISARMED   # when raw is None
```

**[verified]**: with `coordinator.data = None` *and* with an unrecognised raw value, the panel
returns `DISARMED`. For a security panel, "I could not read the state" must never render as
"disarmed" — it hides a live armed system, and any automation keyed on the panel state acts on a
false reading.

Fix: return `None` from `alarm_state` (HA renders `unknown`), change the annotation to
`AlarmControlPanelState | None`, and let read failures propagate so `UpdateFailed` marks the
entity unavailable instead of silently reporting a state.

### H3 — A persistent HTTP 400 yields an empty node list instead of triggering reauth
`api/client.py:145-174`, `182-209`

The session-expiry retry is guarded on `attempt == 0`:

```python
if response.status == 400 and attempt == 0:
    self._session_id = None
    continue
nodes_data = json.loads(response.data)
return nodes_data.get("list", [])
```

On the *second* consecutive 400 the guard is false, so the 400 body is parsed and
`.get("list", [])` returns `[]`. The coordinator records a successful update containing zero
sensors: every entity disappears, `_alarm_node_id` is never discovered, arm/disarm then fails
with "Alarm node not yet discovered", and the reauth flow is never started.

Per `CLAUDE.md` the device returns **400** (not 401) for an expired session, so this is the
*normal* failure path, not an edge case — which also means `async_step_reauth` is effectively
dead code today.

Fix: after the retry budget is spent, raise `ConfigEntryAuthFailed`; and check
`response.status >= 400` before parsing any body. The three methods carry near-identical retry
blocks — worth extracting one `_request_with_retry(method, path, body)` helper.

### H4 — Reloading after an options change breaks the entry
`__init__.py:105-119`

```python
async def async_reload_entry(hass, entry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
```

`entry.async_on_unload` callbacks are run by `ConfigEntry.async_unload()`, *after*
`async_unload_entry` returns — not by `async_unload_platforms`. Calling the module-level
function directly bypasses them, so the webhook is never unregistered. The re-setup then hits
`webhook.async_register`, which raises `ValueError("Handler is already defined!")`.

Fix:

```python
async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
```

Also guard the cleanup on success: `hass.data[DOMAIN].pop(...)` at line 112 runs even when
`unload_ok` is `False`.

### H5 — A second config entry can never be set up
`__init__.py:19`, `71-78`, `85-102`

`WEBHOOK_ID = "qiara_alarm_events"` is a module constant, so entry #2's `async_register` raises
the same `ValueError`. And `_handle_webhook` fans every event out to *every* coordinator:

```python
for event in events:
    for coordinator in coordinators:
        await coordinator.async_push_event(event)
```

so a `node_id` from system A silently mutates system B's data if the ids happen to overlap.

Fix: generate the id with `webhook.async_generate_id()` during the config flow, store it in
`entry.data`, and dispatch only to the owning coordinator. If multi-system support is not a
goal, set `"single_config_entry": true` in the manifest and say so.

### H6 — Camera entities all drive the same node
`camera.py:176-212`

`stream_source`, `async_turn_on`, and `async_turn_off` each call `api.get_camera_node_id()` — a
single cached id — instead of `self._sensor_id`, which *is* the node id the entity was built
from. With two cameras, both entities stream and toggle the same one.
`async_fetch_camera_stream_name` has the same problem: one global `_camera_stream_name` cache.

Fix: use `int(self._sensor_id)` in all four places and key the stream-name cache by node id.

### H7 — `QiaraApi.async_get_sensor_data` always raises
`api/__init__.py:115-124`, `api/client.py:175-180`

It feeds a *raw* node dict (`{"id": 7, "type_name": ..., "adapter_id": ...}`) into
`QiaraSensorData.model_validate`, but the model requires `id: str`, `name: str`, `type: str`.
**[verified]**: `ValidationError: 3 validation errors for QiaraSensorData`. The client-side
helper also re-fetches the entire node list on every call.

Nothing references it today. Delete both, or route the raw dict through `_map_node` first.

### H8 — `manifest.json` omits two used dependencies
`manifest.json:13`

The integration imports `homeassistant.components.webhook` and calls `hass.http.register_view`,
but declares only `["stream"]`. Undeclared dependencies are not guaranteed to be loaded first.

```json
"dependencies": ["http", "stream", "webhook"],
```

### H9 — Untracked background tasks can write state after entity removal
`alarm_control_panel.py:158-162`, `camera.py:114-133`

`hass.async_create_task(self._async_confirm_state(...))` is fire-and-forget: the task is never
cancelled when the entity is removed, so `async_write_ha_state()` can fire against a dead
entity. Two rapid commands also spawn two confirm loops that clobber each other's
`_optimistic_state`. The camera's `_close_after_idle` has the same shape.

Fix: `hass.async_create_background_task(..., name=...)`, keep the handle, cancel any in-flight
task before starting a new one, and cancel in `async_will_remove_from_hass`.

### H10 — No lock around authentication
`api/client.py:117-143`

The coordinator poll, the alarm confirmation loop, and the camera proxy can all reach
`_ensure_session()` concurrently with `_session_id is None` and each fire a separate
`/login/challenge` + `/login/new` pair. Wrap `_authenticate` in an `asyncio.Lock` and re-check
`_session_id` inside it.

---

## Type mapping

### M1 — Integer temperatures are silently dropped
`api/__init__.py:63-66`

The code only reads the dict shape:

```python
if isinstance(raw_temp, dict) and raw_temp.get("value") is not None:
    updates["temperature"] = raw_temp["value"] / 10.0
```

but `openapi.json` documents `temperature` as `type: integer` for `HlDws`, `HlPir`, `HlSrn`, and
`HLKpd`. **[verified]**: a plain `213` maps to `None`, and because `sensor.py:35-36` only
creates the entity when the value is non-None *on the first poll*, the temperature entity is
never created at all. Handle both shapes, and pull the `/10.0` scale factor out as a named
constant.

### M2 — Booleans coerced with bare `bool()`
`api/__init__.py:59-60`, `47`

`bool(ep_map["reachable"])` is correct for the documented `int` 0/1, but **[verified]**
`bool("0")` is `True` — a string-typed device response inverts availability. `_map_node`'s
`not bool(node.get("discarded", 0))` has the same exposure. Add a small helper:

```python
def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no")
    return bool(value)
```

### M3 — A bad battery reading takes down every entity
`api/__init__.py:57-58`

`int(ep_map["battery"])` raises `ValueError` on a non-numeric value. That propagates out of
`_apply_endpoints` → `async_get_sensors` → `UpdateFailed`, so one malformed battery field marks
*all* entities unavailable. Coerce defensively and log-and-skip on failure.

### M4 — `room` overwrites the entity name; `location` is never populated
`api/__init__.py:61-62`, `models.py:17`

`updates["name"] = ep_map["room"].strip()` replaces `"Qiara Door/Window Sensor 12"` with
`"Salon"`, discarding the sensor type — and two sensors in the same room end up with identical
names. `QiaraSensorData.location` exists for exactly this and is never assigned. Put `room` in
`location` and compose the display name, e.g. `f"{room} {label}"`.

### M5 — Three declared sensor types are unreachable
`const.py:13-17`, `api/__init__.py:17-24`, `binary_sensor.py:22-28`

`_NODE_TYPE_MAP` maps `HlDws` to `"door"` unconditionally, so `SENSOR_TYPE_WINDOW` never occurs
— even though the spec exposes an `opening_type` endpoint ("door" or "window") that the code
doesn't read. `smoke` and `co` in `BINARY_SENSOR_TYPES` are likewise unreachable. Either read
`opening_type` and branch on it, or delete the dead constants.

### M6 — The push-event mode mapping is unverified and untested
`coordinator.py:55-60`

```python
"alarm_enabled_full": "day_armed",
"alarm_enabled_partial": "night_armed",
```

Nothing in this repo, in `openapi.json`, or in the tests establishes that "full" means day and
"partial" means night — and the two paths use different vocabularies (the poll path reads
`hl_alarm_status` directly). If this is inverted, the panel silently reports `ARMED_HOME` when
the system is in night mode and vice versa, with no error anywhere. Worth confirming against
`qiara-ha-bridge` and pinning down with a test.

Also, `_ALARM_VALUE_MAP` is rebuilt on every event — hoist it to module scope alongside the
other maps.

### M7 — Naive local timestamps
`coordinator.py:5`, `86`

`datetime.now()` produces a naive local-time value that is surfaced as the `last_triggered`
attribute. HA requires timezone-aware UTC: `homeassistant.util.dt.utcnow()`.

### M8 — `available` returns `None` rather than a bool
`binary_sensor.py:92-96`, `sensor.py:78-82`, `sensor.py:121-125`

```python
return super().available and sensor_data and sensor_data.available
```

**[verified]**: when the sensor is missing from coordinator data this returns `None`, not
`False`, contradicting the `-> bool` annotation. HA treats it as falsy so behaviour is currently
right by accident. Use `bool(...)` and an explicit `is not None` check.

### M9 — Service calls raise `UpdateFailed`
`api/__init__.py:126-150`

`UpdateFailed` is a coordinator-internal signal, not a user-facing service error. Arm/disarm
should raise `HomeAssistantError` (or `ServiceValidationError` for the
"alarm node not yet discovered" case, which is a precondition failure rather than a fault).
This is the silver `action-exceptions` rule. The panel currently re-wraps whatever it gets into
`HomeAssistantError`, which papers over it.

---

## Quality scale gaps

Measured against the current [tier rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

### ~~`config_entry` is not passed to the coordinator~~ — FIXED
`coordinator.py:22-41`

`DataUpdateCoordinator` was constructed without `config_entry`, so it fell back to
`config_entries.current_entry.get()`.

An earlier draft of this review claimed the fallback is removed in HA 2026.8. **That was wrong**
— core explicitly exempts custom integrations:

```python
# It is not planned to enforce this for custom integrations.
frame.report_usage(
    "relies on ContextVar, but should pass the config entry explicitly.",
    core_behavior=frame.ReportBehavior.ERROR,
    core_integration_behavior=frame.ReportBehavior.ERROR,
    custom_integration_behavior=frame.ReportBehavior.IGNORE,
)
```

The real defect was a present-day one. `current_entry` is only populated inside HA's config
entry setup context, and `async_reload_entry` (H4) calls `async_setup_entry` *directly*, outside
it. On every options-triggered reload the coordinator therefore got `config_entry = None`, which:

- makes `async_config_entry_first_refresh()` raise
  `ConfigEntryError("...only supported for coordinators with a config entry")`;
- skips `self.config_entry.async_on_unload(self.async_shutdown)`, leaking the refresh timer
  across reloads.

Fixed by passing the entry explicitly, which removes the dependency on the setup context
altogether. The constructor was also given real annotations (`hass: HomeAssistant`,
`entry: ConfigEntry` — it was previously annotated `dict[str, Any]`) and the class is now
parameterised as `DataUpdateCoordinator[dict[str, Any]]`. The redundant `self.entry` was dropped
in favour of the base class's `self.config_entry`.

Guarded by `tests/custom_components/qiara/test_coordinator.py`.

**Note that H4 still needs its own one-line fix** for reloads to work: passing `config_entry`
stops it being `None`, but `_async_config_entry_first_refresh` also requires the entry to be in
state `SETUP_IN_PROGRESS`, which the manual reload path does not produce.

### Bronze

| Rule | Status |
|---|---|
| `runtime-data` | Uses `hass.data[DOMAIN][entry.entry_id]`. Should be `type QiaraConfigEntry = ConfigEntry[QiaraDataUpdateCoordinator]` + `entry.runtime_data`. |
| `has-entity-name` | No platform sets `_attr_has_entity_name = True` except `camera.py`, which then overrides `name` with the full device name — producing "Salon Salon" in the UI. Set the flag everywhere and `_attr_name = None` for each device's primary entity. |
| `appropriate-polling` | 60 s in `coordinator.py:34`, but `CLAUDE.md` documents 15 s. One of the two is wrong. |
| `common-modules` | The `available` / `device_info` / `_sensor_id` boilerplate is copy-pasted across four entity classes. A shared `entity.py` base removes it. |
| `dependency-transparency` | `openapi_client` is a pinned git SHA. Permitted by the manifest docs, but it isn't on PyPI, which blocks HACS/hassfest-style validation and makes the integration uninstallable where git is unavailable. |
| `docs-*` | No README exists, yet `hacs.json` sets `"render_readme": true`. |

### Silver

| Rule | Status |
|---|---|
| `parallel-updates` | No `PARALLEL_UPDATES = 0` in any platform module. |
| `entity-unavailable` | See H2/H3 — failures render as "disarmed"/empty rather than unavailable. |
| `reauthentication-flow` | `async_step_reauth` exists but is unreachable: the device signals expiry with 400, and the 400 path never raises `ConfigEntryAuthFailed` (H3). |
| `test-coverage` | See below. |

**On the test suite.** 39 tests pass, but they run against a hand-written
`tests/mocks/homeassistant/` package rather than `pytest-homeassistant-custom-component`. There
is no `conftest.py` or pytest config putting `tests/mocks` on `sys.path`, so whether the mocks or
real HA get imported depends on how pytest is invoked — and `CLAUDE.md` documents running inside
Docker, where real HA would shadow them. That ambiguity is worth resolving either way.

The gap it creates is concrete: H1 is *asserted as correct* by
`test_confirm_state_timeout_keeps_optimistic`, because the mock has no notion of a subsequent
coordinator update. There are no tests at all for `__init__.py`, `config_flow.py`,
`coordinator.py`, or `camera.py` — which is where H3, H4, H5, H6, and S1 live. Moving to
`pytest-homeassistant-custom-component` with `MockConfigEntry` and
`hass.config_entries.async_setup` would cover the setup/reload/webhook paths that hold the
worst bugs.

### Gold

Missing: `diagnostics.py`; `entity-translations` (all entity names are hardcoded English strings
built in Python); `icon-translations`; `dynamic-devices` (entity lists are snapshotted from
`coordinator.data` at setup, so a sensor paired later never appears until HA restarts);
`stale-devices`; `reconfiguration-flow` (`async_step_reconfigure` is the modern replacement for
the credentials options flow in `config_flow.py:129-177`).

### Platinum

`strict-typing`: `_ensure_session() -> str` can return `None`. (The coordinator's annotations and
generic parameter were fixed alongside the `config_entry` change above.)

---

## Housekeeping

**Manifest / packaging**

- Missing `"integration_type": "hub"`, `"quality_scale"`, and `"loggers"`.
- `aiohttp>=3.8.0` should not be a requirement — HA ships it, and declaring it risks a resolver
  conflict. `pydantic>=2.0.0` is unpinned; HA requires exact pins.
- `iot_class` is `local_polling`, but there is a webhook push path and the default base URL is a
  cloud endpoint. `local_push` is closer to the truth.
- `hacs.json` pins `"homeassistant": "2024.1.0"`, but the code uses `AlarmControlPanelState`
  (2024.11+) and `ConfigFlowResult` (2024.4+). Raise the floor to at least `2024.11.0`.
- Consider dropping `pydantic` entirely — three small models don't justify the dependency, and
  `dataclasses` is the HA-idiomatic choice.

**Dead code**

`QiaraSystemStatus` (`models.py:30`) and `QiaraSensorList` (imported unused at
`api/__init__.py:12`); the `Field` import in `models.py:7`; `COORDINATOR` in `const.py:4`;
`from typing import Any` in `__init__.py:5`; the duplicated `QiaraApi._base_url`
(`api/__init__.py:75`, also held by the client). `async_migrate_entry` only runs when
`entry.version != VERSION`; with `VERSION = 1` and no prior version, it is unreachable.

**Encapsulation**

`camera.py:36` reads `coordinator.api._base_url`; `api/__init__.py:158` calls
`self._client._ensure_session()`. Both should be public accessors.

**Device registry**

`sensor.py` and `binary_sensor.py` build device identifiers as
`(DOMAIN, f"{entry.entry_id}_{sensor_id}")` with `via_device` pointing at
`(DOMAIN, entry.entry_id)` — but that hub device is created by the alarm panel, and platforms
are forwarded concurrently, so the link may not resolve on first setup. `camera.py:171` uses a
different scheme entirely — `(DOMAIN, self._sensor_id)`, with no `via_device` — so the camera
becomes an orphan device, and two config entries with overlapping node ids would collide on the
same identifier. Also, all four platforms pass plain dicts where `DeviceInfo` is expected
(`alarm_control_panel.py` gets this right).

**Duplicated state**

`binary_sensor.py:82-90` exposes `battery_level` as an attribute *and* as a separate
`QiaraBatterySensor` entity. Drop the attribute.

**Translations**

`strings.json` and `translations/en.json` are byte-identical. `strings.json` is the source of
truth; `en.json` is generated from it.

**Unexposed hardware**

`HlSrn` and `HLKpd` are discovered and mapped, but there is no `siren` platform and no
`event`/`lock` entity for the keypad. Both currently surface only as battery/temperature
diagnostics.

---

## Suggested order of work

1. **S1, S2** — the unauthenticated device-API relay and the disabled TLS verification.
2. **H2, H1** — stop reporting "disarmed" for unknown states, and unstick the optimistic state.
   These are the two findings with real-world safety consequences.
3. ~~**Coordinator `config_entry`**~~ — done.
4. **H3, H4, H8** — the silent-empty-poll bug, the broken reload, the missing dependencies.
   H4 is the other half of the coordinator fix.
5. **M1–M9** — type-mapping fixes, ideally with a regression test each.
6. **H5, H6** — multi-entry and multi-camera correctness, if either is in scope.
7. `runtime-data`, `has-entity-name`, `parallel-updates`, and the move to
   `pytest-homeassistant-custom-component`.
