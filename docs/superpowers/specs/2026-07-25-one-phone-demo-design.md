# One Phone Demo — Design

**Date:** 2026-07-25
**Status:** Awaiting review
**Goal:** One Android phone (emulator `star_trail_emu`) running the Sangam app against a local backend, executing one complete pharma vendor flow that exercises every investor-mandated Sarvam and Razorpay capability, verified with emulator screenshots.

---

## 1. Why this scope

The request spanned seven workstreams (backend, frontend, ease-of-use, autonomous error-free backend, latency, ESP32 firmware, emulator testing). That is too much for one spec. The stated goal — "make it work on just one mobile" — narrows it to a single vertical slice: **one phone, one flow, end to end, demonstrably working.**

ESP32 firmware is explicitly **out of scope** for this spec. It depends on APIs that do not exist yet (vendor, COA, voice-CAPA endpoints). It gets its own spec once those land.

## 2. The demo flow

A single narrative that touches every mandated capability:

1. Operator opens the Sangam app, taps **Add Vendor**
2. Photographs a CDSCO manufacturing licence
3. Backend runs **Sarvam doc-digitization** (`vision_extract` → job poll)
4. **Sarvam LLM** (`llm_complete`) structures the extracted markdown into typed fields
5. Low-confidence fields flagged for human review; the rest auto-populate a `Vendor`
6. A qualification `Workflow` is auto-created in the `APPROVAL` phase
7. Approver reviews on the phone and approves **by voice in Hindi** (**Sarvam STT**)
8. Approval triggers a **Razorpay UPI** advance held in **escrow**
9. Goods delivered → handoff verified → **escrow auto-releases**
10. Confirmation **spoken back in Hindi** (**Sarvam TTS**)

Capability coverage: Sarvam doc-intelligence, LLM, STT, TTS. Razorpay orders, UPI intent, escrow, webhooks.

## 3. Slices

### Slice 0 — Make it run, make it safe

Prerequisite for everything. Nothing can be tested until the backend boots.

| Item | Detail |
|---|---|
| `git init` | With `.gitignore` covering `venv/`, `node_modules/`, `.env`, `*.db`, `build/`, `.gradle/`, `__pycache__/`, `*_test_results.json`, `dist/` |
| `.env` | Written **after** gitignore exists, so secrets are never committable |
| Backend boot | Via `docker-compose up`. Host Python is 3.14.6; `requirements.txt` targets 3.12 with pinned async stacks, so Docker is the reliable path |
| **Webhook HMAC** | `POST /payments/webhook` currently has zero signature verification (`app/api/payments.py:256`). Anyone can forge `payment.captured`. Add `X-Razorpay-Signature` HMAC-SHA256 validation against a webhook secret |
| **`eval()` removal** | `ConditionEvaluator.evaluate` (`app/core/coordinator.py:257`) runs `eval()` on workflow-supplied strings. Replace with a restricted comparison evaluator over an explicit AST allowlist |
| **Duplicate router** | `govstack_router` is imported and included twice (`app/main.py:24-25`, `:75-76`), registering every GovStack route twice |
| Health gate | `GET /health` returns 200 and `/docs` renders before the slice is considered done |

**Exit criteria:** `docker-compose up` → `/health` 200 → `pytest tests/` green.

### Slice 1 — Vendor/COA domain + Sarvam pipeline

No vendor, licence, or document models exist today — only actor/workflow/approval/handoff/exception/payment/sla. The entire pharma value proposition has no domain model behind it.

**New models** (`app/models/vendor.py`, `app/models/document.py`):
- `Vendor` — name, GSTIN, PAN, address, `VendorStatus` (draft/pending_qualification/qualified/suspended/rejected), linked `Actor`
- `VendorLicence` — type (CDSCO/State FDA/GST/MCA), number, issue/expiry dates, issuing authority, verification status
- `ExtractedDocument` — source file ref, Sarvam job id, raw extracted markdown, structured JSON, per-field confidence, `needs_review` flag

**New service** (`app/core/document_intelligence.py`) — chains the existing primitives, which are currently only reachable as disconnected API endpoints:
```
upload → vision_extract (job) → poll status → fetch markdown
       → llm_complete (structured extraction w/ JSON schema prompt)
       → per-field confidence → persist → flag low-confidence for review
```

**New API** (`app/api/vendors.py`): create, list, get, `POST /vendors/{id}/documents` (upload+extract), `POST /vendors/{id}/submit-for-qualification` (creates the approval workflow).

**Design decision:** doc-digitization is asynchronous (job submit → poll). The upload endpoint returns immediately with a job id; the phone polls a status endpoint. Blocking the request for up to 300s would time out the mobile client.

### Slice 2 — Razorpay lifecycle

`release_escrow` exists in `app/core/payments.py:277` but **nothing calls it**. Escrow that requires a manual API call to release defeats its purpose.

- Wire `Coordinator.verify_handoff` → `PaymentManager.release_escrow` when a workflow has a held escrow whose release condition is satisfied
- UPI intent order creation callable from the phone (`create_upi_intent_order` already exists, unused by any client)
- Webhook signature verification (from Slice 0) proven with a signed-payload test

**Deliberately deferred:** RazorpayX payouts and Smart Collect virtual accounts. Both are strong fits for the CFO/TDS pain point but neither is needed for the one-phone demo, and payouts move real money — they warrant their own spec and their own risk review.

### Slice 3 — Android + screenshots

- **New screens:** `VendorListScreen`, `VendorDetailScreen`, `AddVendorScreen` (camera/file capture)
- **Existing stubs finished:** `VoiceWorkflowScreen` (record → STT → approve), `PaymentScreen` (UPI intent)
- TTS playback of the confirmation
- Build with Gradle, install to `star_trail_emu`, screenshot each step of the flow

`API_BASE_URL` is already `http://10.0.2.2:8000` — the emulator's host-localhost alias — so the app is pre-wired to a backend on the dev machine. No change needed.

## 4. Credentials and fixture mode

**Razorpay keys supplied were `rzp_live_` (production).** They will not be used. Live keys in an automated build/test loop risk real money movement, especially given Slice 2 makes escrow release *automatic*. Razorpay runs on fixtures until `rzp_test_` keys are supplied.

**Fixture mode** — when a key is absent or fixture mode is forced, the Sarvam and Razorpay clients return realistic canned responses (a plausible extracted CDSCO licence, a plausible UPI order) through **identical code paths**. Benefits:
- The demo runs end-to-end without live credentials
- Tests are hermetic — no network, no spend, deterministic
- Swapping in real keys is config-only, no code change

Sarvam uses the live key (metered AI spend, not money movement).

## 5. Error handling and latency

**Autonomous/error-free** is interpreted concretely as:
- Every external call (Sarvam, Razorpay) wrapped in the existing `retry_async` with bounded exponential backoff
- Failures degrade to a review task rather than a crashed workflow — a failed extraction produces a `needs_review` document, not a 500
- The existing `GlobalExceptionHandler` returns structured errors with the request id already provided by `RequestIDMiddleware`
- **Latency:** `settings.api_p99_target_ms` is 100ms and currently unenforced. Add timing to the logging middleware and assert the vendor-list and approval endpoints stay under target with fixtures. Doc-digitization is explicitly exempt — it is a long-running job by design, which is why it is async.

## 6. Testing

- Unit: document-intelligence extraction against fixture payloads; escrow release logic; the replacement condition evaluator (including that it rejects the injection strings the old `eval()` accepted)
- Integration: full flow via `httpx` ASGI transport against the SQLite test DB (existing `conftest.py` pattern)
- Webhook: signed and deliberately-unsigned payloads, asserting forged events are rejected
- Manual: emulator run with screenshots at each step

## 7. Out of scope

ESP32 firmware · RazorpayX payouts · Smart Collect · GovStack expansion · capability-discovery/Qdrant marketplace · MCP servers · web dashboard rework (phone is the target) · NPPA/ADR modules

## 8. Open questions

1. `rzp_test_` keys — needed before Slice 2 runs against live Razorpay
2. Rotation of the exposed credentials
3. Whether a real CDSCO licence sample is available for extraction accuracy testing, or whether a synthetic one should be generated
