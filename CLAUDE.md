# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Sangam is an AI-native coordination platform: organizations, AI agents, humans, services, and software discover, communicate, negotiate, orchestrate workflows, exchange structured data, manage approvals, and handle exceptions through a unified API.

```
backend/   Python FastAPI + Temporal (workflow engine) — the core system
android/   Jetpack Compose (Material 3 Expressive) client
web/       React 19 + Refine + shadcn/ui dashboard
sdk/       python/ and typescript/ client SDKs
k8s/       Kubernetes manifests (ArgoCD-ready)
```

## Commands

### Backend (from `backend/`)

```bash
python -m venv venv && source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example .env
python -m scripts.seed_demo                          # SQLite tables + demo user + sample vendor
python -m uvicorn app.main:app --reload              # dev server, http://localhost:8000/docs
python -m scripts.demo_flow                          # end-to-end flow, prints per-step latency
pytest tests/ -v                                     # full test suite
pytest tests/test_api.py::test_name -v                # single test
pytest tests/ -v --cov=app --cov-report=term          # with coverage (matches CI)
ruff check app/ --fix                                 # lint
mypy app/ --ignore-missing-imports                     # type check
alembic revision --autogenerate -m "message"           # new migration
alembic upgrade head                                    # apply migrations
```

Tests run against SQLite (`test_sangam.db`, via `tests/conftest.py`), not Postgres — no external services needed to run `pytest`. Root-level `test_*.py` and `*_test_results.json` files in `backend/` are ad-hoc integration/stress scripts (Razorpay, GovStack, Sarvam, e2e, load) run manually against a live stack, separate from `tests/`.

### Web dashboard (from `web/`)

```bash
npm install
npm run dev       # vite dev server
npm run build     # tsc -b && vite build
npm run lint
```

### Full stack via Docker

```bash
docker-compose up -d   # Postgres, Redis, RabbitMQ, Temporal, backend
```

### Android

Open `android/` in Android Studio; run on emulator/device. Or `./gradlew build` from `android/`.

CI (`.github/workflows/ci.yml`) runs backend lint/typecheck/test and web build/lint on every push/PR to `main`/`develop`; `develop` pushes additionally trigger a staging deploy step.

## Architecture

### Workflow lifecycle (backend)

The domain model centers on `Workflow` (`app/models/workflow.py`), which moves through a fixed set of **phases** (`WorkflowPhase`: initiation → approval → execution → verification → settlement, plus `exception`) independently of its **state** (`WorkflowState`: draft, active, paused, completed, failed). `Coordinator` (`app/core/coordinator.py`) is the central orchestration class — it drives phase transitions, creates/verifies actor-to-actor `Handoff`s, runs parallel/conditional execution patterns, and creates `WaitingEvent`s (SLA-bound pauses). Any failure or timeout routes through `_handle_exception`, which spins up a bounded `ExceptionWorkflow` rather than failing the parent workflow outright.

Durable/long-running execution is delegated to **Temporal** (`app/core/temporal_setup.py`, `app/core/workflow_engine.py`) — Temporal activities and workflow definitions live alongside but separate from the synchronous `Coordinator` path used by the HTTP API; `workflow.unsafe.imports_passed_through()` is used to bring app models into the Temporal sandbox.

**Actors** (`app/models/actor.py`) are the uniform participant type — human, AI agent, or system — and are first-class on workflows, approvals, and handoffs alike. **Approvals** (`app/core/approval_engine.py`) support any/all/threshold multi-party strategies with conditional rules and escalation.

### Capability discovery & semantic boundaries

`app/core/capability_discovery.py` indexes registered capabilities (APIs, MCP servers, agents, webhooks) in Qdrant for semantic search-based discovery, scored on trust/latency/cost. `app/core/semantic_boundary.py` uses Sarvam AI (`app/core/sarvam.py`) to detect points where a workflow crosses trust/regulatory/security boundaries (data privacy, financial approval, cross-domain transfer, etc.) and suggest required actions — this is an LLM-backed classifier, not a static rules engine.

### MCP integration

`app/mcp_servers/` implements the Model Context Protocol server side (`base.py`: `MCPServer`/`MCPTool`/registration/dispatch) with concrete servers for GitHub, SAP, and Slack (`registry.py` wires them up), exposed via `app/api/mcp.py`. This lets external MCP clients (including AI agents) discover and invoke Sangam-registered capabilities as tools.

### API layer

FastAPI app assembly is in `app/main.py`: one router per domain area (`app/api/*.py` — workflows, actors, approvals, coordination, payments, templates, mcp, auth, ws, analytics, notifications, autonomous, govstack, sarvam_ai, capabilities). Cross-cutting concerns (request ID, structured logging, rate limiting, global exception handling) are applied as middleware in `app/core/middleware.py`. Config is a single `pydantic-settings` `Settings` object (`app/config.py`) reading from `.env`; most integrations (Razorpay, Sarvam, Zitadel, FCM, email, Slack) are optional and no-op/absent when their keys aren't set.

`app/api/govstack.py` and `app/core/govstack.py` implement GovStack-compatible building-block endpoints for interop with government digital infrastructure — treat these as a distinct compliance surface from the core workflow API.

### Frontend (web)

React 19 + Refine (`@refinedev/core` with `simple-rest` data provider pointed at `VITE_API_URL`, default `/api/v1`) + React Router. `src/lib/api.ts` is a thin typed fetch wrapper (bearer token from `localStorage`, redirects to `/login` on 401) — prefer extending this over adding a second HTTP client. Pages under `src/pages/` map roughly 1:1 to backend routers (Dashboard, WorkflowList/Detail, Approvals, Actors, Templates, Capabilities); `src/components/workflow-builder/` is the workflow authoring UI.

### Android

Jetpack Compose, single-activity (`MainActivity.kt` → `SangamNavHost.kt`), package `com.sangam.app`. `network/` holds the Retrofit-style API/auth layer (`ApiService`, `AuthApi`, `AuthInterceptor`, `TokenManager`, `RealtimeClient` for WS/live updates); `notification/SangamFirebaseService.kt` handles FCM push. Screens under `ui/screens/` mirror the web pages plus mobile-specific ones (VoiceWorkflowScreen, AIAssistantScreen, PaymentScreen).

### SDKs

`sdk/python/sangam_sdk.py` and `sdk/typescript/sangam-client.ts` are thin, single-file client wrappers over the same `/api/v1` surface consumed by web/android — check these when the public API contract changes, since they're not auto-generated from the OpenAPI schema.

## External integrations

`SARVAM_API_KEY` and `RAZORPAY_*` live in `backend/.env` (gitignored). **Never use `rzp_live_` keys in development** — escrow release is automatic, so a logic bug moves real money. Test keys start with `rzp_test_`.

**Fixture mode** (`app/core/fixtures.py`): when a service's credentials are absent or `USE_FIXTURES=true`, the Sarvam and Razorpay clients return deterministic canned responses through identical code paths. `tests/conftest.py` forces it on suite-wide — without that, tests make billable Sarvam calls and reach a live gateway. Enabling live keys is a config change, never a code change.

Four integration shapes are easy to get wrong and are documented in code comments where they matter:
- Sarvam doc digitisation needs create → `upload-files` → PUT to the presigned Azure blob (`x-ms-blob-type: BlockBlob`) → `start`. Status reports `job_state`; output is a ZIP fetched via `POST {job_id}/download-files`.
- `sarvam-30b` is a reasoning model: budget `max_tokens` generously (4096 is the starter-tier ceiling) or `content` comes back null.
- Razorpay Orders takes `method` as a **string**; a nested object is rejected.
- Sarvam Voice Agents (Samvaad, `app/core/samvaad.py`, routes in `app/api/voice_agents.py`) use `SARVAM_SAMVAAD_API_KEY` in an `X-API-Key` header, a different key from `SARVAM_API_KEY`. Each service has its own base under `https://apps.sarvam.ai/api`, and calls need `SAMVAAD_ORG_ID`/`SAMVAAD_WORKSPACE_ID`. Outbound calls return only an `attempt_id`; the outcome arrives on an **unsigned** webhook, so each call gets its own secret webhook URL. The app never holds the key: it streams PCM to `/voice-agents/ws/{app_id}` and the server runs the SDK session.

## Conventions worth preserving

- Workflow conditions run through `app/core/safe_eval.py` (AST allowlist). Never reintroduce `eval()` — conditions are attacker-influenced data.
- `POST /payments/webhook` is authenticated solely by its HMAC signature over the **raw** request bytes. Do not parse the body into a Pydantic model before verifying; re-serialising changes the digest.
- Model classes must be imported in `app/models/__init__.py` or `Base.metadata.create_all` silently skips their tables.
- Extractions below `CONFIDENCE_REVIEW_THRESHOLD` are never auto-promoted to licences; a human confirms them. A mis-read expiry date means shipping against a lapsed licence.
- Android debug builds need `src/debug/res/xml/network_security_config.xml` to reach a local HTTP backend; keep cleartext scoped to loopback so release stays HTTPS-only.
