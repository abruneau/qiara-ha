# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A Home Assistant custom integration for Qiara security systems. It polls a local Qiara device over HTTPS, maps its nodes (alarm hub, door/window sensors, PIR sensors, siren, keypad, camera) into HA entities, and exposes arm/disarm control via the `alarm_control_panel` platform.

## Development environment

The integration runs inside a Docker container with HA mounted live:

```bash
docker compose up -d          # start HA at http://localhost:8123
docker compose restart        # reload after code changes (no rebuild needed)
docker compose logs -f        # tail HA logs
```

Code changes to `custom_components/qiara/` are picked up on the next HA restart — no image rebuild required. The volume mount is `./custom_components/qiara:/config/custom_components/qiara`.

## Running tests

Local python environment use venv
```bash
source .venv/bin/activate
```

Tests use `pytest-asyncio` and mock all HA and API dependencies — **no live device or HA instance needed**. Tests run inside the Docker container where `homeassistant` is installed:

```bash
python -m pytest ./custom_components/../tests/ -q
# or a single test file:
python -m pytest ./custom_components/../tests/custom_components/qiara/test_alarm_control_panel.py -v
```

Tests do **not** use a `conftest.py` — each module defines its own `pytest.fixture` functions inline.

## Architecture

### Data flow

```
QiaraApiClient (api/client.py)
  → raw HTTP (aiohttp, HMAC-SHA1 auth, session caching)
  → returns plain dicts

QiaraApi (api/__init__.py)
  → wraps QiaraApiClient
  → maps raw node dicts to QiaraSensorData (Pydantic) and string alarm state
  → raises UpdateFailed / ConfigEntryAuthFailed for HA to handle

QiaraDataUpdateCoordinator (coordinator.py)
  → polls every 15 s via _async_update_data()
  → returns dict[str, Any]:
      sensor_id → QiaraSensorData   (one entry per sensor node)
      "alarm_state" → str | None    (special key: "off", "day_armed", "night_armed")

Platform entities (alarm_control_panel, binary_sensor, sensor)
  → extend CoordinatorEntity
  → read coordinator.data in properties
  → guard against the "alarm_state" string key: isinstance(v, QiaraSensorData)
```

### Real Qiara API (differs from OpenAPI spec)

- Auth: `GET /login/challenge` → HMAC-SHA1 → `POST /login/new` → session ID in `x-hlcore-session-id` header
- Device returns **400** (not 401) for expired sessions — all three API methods retry once on 400
- Node list: `POST /home/nodes` with body `{"hash_i": 0}` (spec says GET)
- Read endpoints: `POST /home/endpoints_read` with `{"list": [{"node_id": N, "eps": [...]}]}`
- Write endpoints: `POST /home/endpoints_write` with `{"list": [{"node_id": N, "eps": [{"ep_name": "...", "value": "..."}]}]}`
- API returns HTTP 200 even on write failure — check `success: 0` in the response body
- Alarm arm: write `hl_alarm_enable` with `"day"` or `"night"` (NOT `hl_alarm_status`)
- Alarm disarm: write `hl_alarm_disable` with `""` (empty string)
- Alarm state read: `hl_alarm_status` returns `"off"`, `"day_armed"`, `"night_armed"` (spec enum is wrong)

### Node types

| `type_name` | mapped type | has `adapter_id` |
|---|---|---|
| `Node.HlAlarm` | alarm | no |
| `Node.HlCam` | camera | no |
| `Node.DomusNode.HlDws` | door | yes |
| `Node.DomusNode.HlPir` | motion | yes |
| `Node.DomusNode.HlSrn` | siren | yes |
| `Node.DomusNode.HLKpd` | keypad | yes |

DomusNodes (have `adapter_id`) support live endpoint reads for `state`, `battery`, `reachable`, `room`, `temperature`. The alarm node ID is discovered dynamically from the nodes list and cached as `_alarm_node_id` in `QiaraApi`.

### Alarm control panel state

The panel uses **optimistic state** immediately after arm/disarm commands (for UI responsiveness), then transitions to coordinator-driven state once the next poll completes. Both paths go through `_ALARM_STATE_MAP` in `alarm_control_panel.py`.

## Project status tracking

Sprint and epic status is tracked in `_bmad-output/implementation-artifacts/sprint-status.yaml`. Story files (implementation artifacts) are in `_bmad-output/implementation-artifacts/`. Architecture decisions are in `_bmad-output/planning-artifacts/architecture.md`.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->