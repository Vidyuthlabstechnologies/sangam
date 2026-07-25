# One Phone Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working end-to-end pharma vendor-onboarding flow on one Android phone, exercising Sarvam (doc-intelligence, LLM, STT, TTS) and Razorpay (UPI, escrow), with emulator screenshots as VC-presentable evidence.

**Architecture:** FastAPI backend (async SQLAlchemy + Temporal) gains a Vendor/Licence/Document domain and a document-intelligence service chaining Sarvam's existing primitives. Razorpay escrow release becomes event-driven off handoff verification. The existing Jetpack Compose app gains vendor screens and finishes its stubbed voice/payment screens. A fixture layer makes every external call deterministic and offline-testable.

**Tech Stack:** Python 3.12 (Docker), FastAPI, SQLAlchemy 2 async, Alembic, pytest/pytest-asyncio, httpx; Kotlin/Jetpack Compose, Gradle, Android SDK 35; Sarvam API, Razorpay test API.

---

## Reference: Existing Code Map

Read before starting. These are the touch points.

| Concern | Location |
|---|---|
| App assembly, router includes | `backend/app/main.py` |
| Settings (pydantic-settings) | `backend/app/config.py` |
| Sarvam client (STT/TTS/LLM/vision) | `backend/app/core/sarvam.py` |
| Razorpay client + escrow | `backend/app/core/payments.py` |
| Orchestration, handoffs, `eval()` | `backend/app/core/coordinator.py` |
| Declarative base | `backend/app/db/base.py` |
| Session dependency | `backend/app/db/session.py` |
| Auth dependency | `backend/app/api/dependencies.py` |
| Test fixtures (SQLite) | `backend/tests/conftest.py` |
| Android API layer | `android/app/src/main/java/com/sangam/app/network/ApiService.kt` |
| Android nav | `android/app/src/main/java/com/sangam/app/ui/navigation/SangamNavHost.kt` |

## File Structure

**Create:**
- `.gitignore` — repo hygiene, must exist before `.env`
- `backend/.env` — secrets, never committed
- `backend/app/core/fixtures.py` — deterministic canned responses for Sarvam/Razorpay
- `backend/app/core/safe_eval.py` — AST-allowlist condition evaluator replacing `eval()`
- `backend/app/models/vendor.py` — `Vendor`, `VendorLicence`
- `backend/app/models/document.py` — `ExtractedDocument`
- `backend/app/schemas/vendor.py` — request/response models
- `backend/app/core/document_intelligence.py` — Sarvam extraction pipeline
- `backend/app/api/vendors.py` — vendor routes
- `backend/tests/test_safe_eval.py`, `test_webhook_security.py`, `test_document_intelligence.py`, `test_vendor_api.py`, `test_escrow_release.py`
- Android: `ui/screens/VendorListScreen.kt`, `VendorDetailScreen.kt`, `AddVendorScreen.kt`

**Modify:**
- `backend/app/main.py` — remove duplicate govstack include, add vendors router
- `backend/app/config.py` — webhook secret, fixture-mode flag
- `backend/app/core/coordinator.py` — swap `eval()`, trigger escrow release
- `backend/app/core/payments.py` — webhook signature verification
- `backend/app/api/payments.py` — verified webhook endpoint
- `backend/app/core/sarvam.py` — fixture-mode short-circuit
- `backend/app/models/__init__.py` — register new models
- Android `network/ApiService.kt`, `ui/navigation/SangamNavHost.kt`

---

# SLICE 0 — Make it run, make it safe

## Task 1: Version control and secrets hygiene

**Files:**
- Create: `.gitignore`
- Create: `backend/.env`

- [ ] **Step 1: Initialise the repo**

```bash
cd "C:/Users/varsh/OneDrive/Documents/0001Sangam"
git init
git config core.autocrlf false
```

- [ ] **Step 2: Write `.gitignore` BEFORE any secret exists on disk**

```
# Python
__pycache__/
*.py[cod]
venv/
.venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Secrets
.env
*.env
!.env.example

# Databases
*.db
*.sqlite3

# Node
node_modules/
dist/

# Android
.gradle/
build/
local.properties
*.apk
*.aab
.kotlin/

# Test artefacts
*_test_results.json

# OS
.DS_Store
Thumbs.db

# Scratch
.remember/tmp/
.remember/logs/
```

- [ ] **Step 3: Verify `.env` would be ignored, then write it**

```bash
git check-ignore -v backend/.env
```
Expected: prints a `.gitignore` rule match. If it prints nothing, STOP — the file would be committed.

Then create `backend/.env` with the Sarvam key, Razorpay **test** keys, a generated `JWT_SECRET`, and `RAZORPAY_WEBHOOK_SECRET`. Values come from the operator, never from this plan.

- [ ] **Step 4: First commit**

```bash
git add -A
git status --short | head -30
git commit -m "chore: initialise repository with gitignore"
```
Expected: `backend/.env` absent from the staged list.

## Task 2: Remove the duplicate GovStack router

**Files:**
- Modify: `backend/app/main.py:24-25`, `backend/app/main.py:75-76`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_app_wiring.py`:
```python
from app.main import app


def test_no_duplicate_routes():
    seen = {}
    for route in app.routes:
        key = (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", []) or [])))
        seen[key] = seen.get(key, 0) + 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, f"Duplicate routes registered: {duplicates}"
```

- [ ] **Step 2: Run it, confirm failure**

Run: `pytest tests/test_app_wiring.py -v`
Expected: FAIL listing duplicated `/govstack/...` paths.

- [ ] **Step 3: Delete the duplicate lines**

In `backend/app/main.py`, delete the second `from app.api.govstack import router as govstack_router` (line 25) and the second `app.include_router(govstack_router)` (line 76). One of each remains.

- [ ] **Step 4: Confirm pass**

Run: `pytest tests/test_app_wiring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_app_wiring.py
git commit -m "fix: remove duplicate govstack router registration"
```

## Task 3: Replace `eval()` with an AST-allowlist evaluator

`ConditionEvaluator.evaluate` runs `eval()` on workflow-supplied strings. `{"__builtins__": {}}` is not a sandbox.

**Files:**
- Create: `backend/app/core/safe_eval.py`
- Create: `backend/tests/test_safe_eval.py`
- Modify: `backend/app/core/coordinator.py:249-259`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_safe_eval.py`:
```python
import pytest
from app.core.safe_eval import safe_evaluate, UnsafeExpressionError


def test_simple_comparison():
    assert safe_evaluate("amount > 100", {"amount": 500}) is True
    assert safe_evaluate("amount > 100", {"amount": 50}) is False


def test_boolean_logic():
    ctx = {"approved": True, "amount": 5000}
    assert safe_evaluate("approved and amount < 10000", ctx) is True


def test_membership_and_equality():
    ctx = {"status": "qualified", "tags": ["cdsco", "gmp"]}
    assert safe_evaluate("status == 'qualified'", ctx) is True
    assert safe_evaluate("'gmp' in tags", ctx) is True


def test_missing_variable_is_false_not_crash():
    assert safe_evaluate("nonexistent > 5", {}) is False


def test_empty_condition_is_true():
    assert safe_evaluate("", {}) is True


@pytest.mark.parametrize("attack", [
    "__import__('os').system('echo pwned')",
    "().__class__.__bases__[0].__subclasses__()",
    "open('/etc/passwd').read()",
    "lambda: 1",
    "[x for x in range(10)]",
])
def test_rejects_code_execution(attack):
    with pytest.raises(UnsafeExpressionError):
        safe_evaluate(attack, {})
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_safe_eval.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.safe_eval`

- [ ] **Step 3: Implement**

`backend/app/core/safe_eval.py`:
```python
from __future__ import annotations
import ast
import operator
from typing import Any, Dict


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses constructs outside the allowlist."""


_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}

_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.BinOp, ast.Compare, ast.Name, ast.Load, ast.Constant,
    ast.List, ast.Tuple,
) + tuple(_BIN_OPS) + tuple(_CMP_OPS)


class _Evaluator(ast.NodeVisitor):
    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def visit(self, node):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpressionError(
                f"Disallowed expression element: {type(node).__name__}"
            )
        return super().visit(node)

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        return self.context.get(node.id, _MISSING)

    def visit_List(self, node):
        return [self.visit(e) for e in node.elts]

    def visit_Tuple(self, node):
        return tuple(self.visit(e) for e in node.elts)

    def visit_UnaryOp(self, node):
        if not isinstance(node.op, ast.Not):
            raise UnsafeExpressionError("Only 'not' unary operator permitted")
        return not self.visit(node.operand)

    def visit_BoolOp(self, node):
        values = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    def visit_BinOp(self, node):
        fn = _BIN_OPS.get(type(node.op))
        if fn is None:
            raise UnsafeExpressionError(f"Disallowed operator: {type(node.op).__name__}")
        left, right = self.visit(node.left), self.visit(node.right)
        if left is _MISSING or right is _MISSING:
            return _MISSING
        return fn(left, right)

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            fn = _CMP_OPS.get(type(op))
            if fn is None:
                raise UnsafeExpressionError(f"Disallowed comparison: {type(op).__name__}")
            right = self.visit(comparator)
            if left is _MISSING or right is _MISSING:
                return False
            if not fn(left, right):
                return False
            left = right
        return True

    def generic_visit(self, node):
        raise UnsafeExpressionError(f"Disallowed expression element: {type(node).__name__}")


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


def safe_evaluate(condition: str, context: Dict[str, Any]) -> bool:
    """Evaluate a workflow condition without executing arbitrary code.

    Unknown variables evaluate falsey rather than raising, so a condition
    referencing absent workflow context degrades to False instead of a 500.
    Raises UnsafeExpressionError for anything outside the allowlist.
    """
    if not condition or not condition.strip():
        return True
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid condition syntax: {exc}") from exc
    result = _Evaluator(context).visit(tree)
    if result is _MISSING:
        return False
    return bool(result)
```

- [ ] **Step 4: Confirm pass**

Run: `pytest tests/test_safe_eval.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Wire into Coordinator**

In `backend/app/core/coordinator.py`, replace the `ConditionEvaluator` class body so `evaluate` delegates:

```python
from app.core.safe_eval import safe_evaluate, UnsafeExpressionError


class ConditionEvaluator:
    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def evaluate(self, condition: str) -> bool:
        try:
            return safe_evaluate(condition, self.context)
        except UnsafeExpressionError:
            return False
```

- [ ] **Step 6: Full suite, then commit**

```bash
pytest tests/ -v
git add backend/app/core/safe_eval.py backend/app/core/coordinator.py backend/tests/test_safe_eval.py
git commit -m "fix: replace eval() in condition evaluation with AST allowlist"
```

## Task 4: Razorpay webhook signature verification

`POST /payments/webhook` accepts unauthenticated events. A forged `payment.captured` marks a real payment captured.

**Files:**
- Modify: `backend/app/config.py`, `backend/app/core/payments.py`, `backend/app/api/payments.py:251-265`
- Create: `backend/tests/test_webhook_security.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_webhook_security.py`:
```python
import hmac
import hashlib
import json
import pytest

WEBHOOK_SECRET = "test_webhook_secret"


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_unsigned_webhook_rejected(client):
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    resp = await client.post(
        "/payments/webhook", content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bad_signature_rejected(client):
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    resp = await client.post(
        "/payments/webhook", content=body,
        headers={"X-Razorpay-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_signature_accepted(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "razorpay_webhook_secret", WEBHOOK_SECRET)
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    resp = await client.post(
        "/payments/webhook", content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_webhook_security.py -v`
Expected: FAIL — endpoint returns 200 for unsigned payloads.

- [ ] **Step 3: Add the setting**

In `backend/app/config.py`, inside `Settings`:
```python
    razorpay_webhook_secret: Optional[str] = None
    use_fixtures: bool = False
```

- [ ] **Step 4: Add verification helper**

In `backend/app/core/payments.py`, on `RazorpayService`:
```python
    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
        secret = settings.razorpay_webhook_secret
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
```

- [ ] **Step 5: Rewrite the endpoint to read the raw body**

Replace the webhook handler in `backend/app/api/payments.py`. Signature is computed over exact bytes, so the raw body must be read before JSON parsing:

```python
from fastapi import Request, Header


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Razorpay webhook. Authenticated by HMAC signature, not by session auth."""
    raw_body = await request.body()

    if not RazorpayService.verify_webhook_signature(raw_body, x_razorpay_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    manager = PaymentManager(session)
    await manager.handle_webhook(data.get("event", ""), data.get("payload", {}))
    return {"status": "received"}
```

Add `import json` to the module imports.

- [ ] **Step 6: Confirm pass, commit**

```bash
pytest tests/test_webhook_security.py -v
git add backend/app/api/payments.py backend/app/core/payments.py backend/app/config.py backend/tests/test_webhook_security.py
git commit -m "fix: verify Razorpay webhook HMAC signatures"
```

## Task 5: Fixture mode for external services

Makes tests hermetic and lets the demo run without live spend.

**Files:**
- Create: `backend/app/core/fixtures.py`
- Modify: `backend/app/core/sarvam.py`, `backend/app/core/payments.py`

- [ ] **Step 1: Write the fixture module**

`backend/app/core/fixtures.py`:
```python
"""Deterministic canned responses for external services.

Active when a service's credentials are absent or settings.use_fixtures is True.
Identical code paths run in both modes, so enabling live credentials is a
config change, never a code change.
"""
from __future__ import annotations
import base64
from typing import Any, Dict

CDSCO_LICENCE_MARKDOWN = """# FORM 25
## LICENCE TO MANUFACTURE FOR SALE OR FOR DISTRIBUTION OF DRUGS

**Licence Number:** MFG/25/2024/KA/00847
**Issued to:** Meridian Life Sciences Private Limited
**Address:** Plot 14, Industrial Area Phase II, Peenya, Bengaluru 560058, Karnataka
**Issuing Authority:** Drugs Control Department, Government of Karnataka
**Date of Issue:** 14/03/2024
**Valid Until:** 13/03/2029
**Categories:** Tablets, Capsules, Oral Liquids
**Competent Person:** Dr. S. Ramachandran, M.Pharm
"""

EXTRACTED_LICENCE_JSON = {
    "licence_number": "MFG/25/2024/KA/00847",
    "vendor_name": "Meridian Life Sciences Private Limited",
    "address": "Plot 14, Industrial Area Phase II, Peenya, Bengaluru 560058, Karnataka",
    "issuing_authority": "Drugs Control Department, Government of Karnataka",
    "issue_date": "2024-03-14",
    "expiry_date": "2029-03-13",
    "licence_type": "CDSCO",
    "categories": ["Tablets", "Capsules", "Oral Liquids"],
    "confidence": {
        "licence_number": 0.97, "vendor_name": 0.95, "address": 0.88,
        "issuing_authority": 0.93, "issue_date": 0.96, "expiry_date": 0.96,
    },
}

# 0.1s of silence, 24kHz mono WAV — valid audio the phone can actually play.
_SILENT_WAV = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\xc0\x5d\x00\x00\x80\xbb\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


def sarvam_vision_job() -> Dict[str, Any]:
    return {"job_id": "fixture-job-0001", "storage_container": {"upload_url": ""}}


def sarvam_vision_status(job_id: str) -> Dict[str, Any]:
    return {"job_id": job_id, "status": "completed", "output": CDSCO_LICENCE_MARKDOWN}


def sarvam_stt(language_code: str = "hi-IN") -> Dict[str, Any]:
    return {
        "transcript": "मैं इस विक्रेता को मंजूरी देता हूं",
        "language_code": language_code,
        "language_probability": 0.94,
    }


def sarvam_tts() -> Dict[str, Any]:
    return {
        "audios": [base64.b64encode(_SILENT_WAV).decode()],
        "request_id": "fixture-tts-0001",
    }


def sarvam_llm(content: str) -> Dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def razorpay_order(amount_paise: int, receipt: str) -> Dict[str, Any]:
    return {
        "id": "order_FIXTURE00001", "entity": "order", "amount": amount_paise,
        "currency": "INR", "receipt": receipt, "status": "created",
    }


def razorpay_payment(payment_id: str = "pay_FIXTURE00001") -> Dict[str, Any]:
    return {"id": payment_id, "entity": "payment", "status": "captured", "method": "upi"}
```

- [ ] **Step 2: Short-circuit Sarvam when no key is configured**

In `backend/app/core/sarvam.py`, relax `__init__` so a missing key enables fixture mode instead of raising:

```python
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.sarvam_api_key or os.environ.get("SARVAM_API_KEY", "")
        self.use_fixtures = settings.use_fixtures or not self.api_key
```

Then guard each network method. For `text_to_speech`, after validation and before the HTTP call:

```python
        if self.use_fixtures:
            data = fixtures.sarvam_tts()
            audios = data.get("audios", [])
            return SarvamTTSResult(
                audio_base64=audios[0] if audios else "",
                request_id=data.get("request_id", ""),
            )
```

Apply the equivalent guard in `speech_to_text` (→ `fixtures.sarvam_stt`), `vision_extract` (→ `fixtures.sarvam_vision_job`), and `vision_job_status` (→ `fixtures.sarvam_vision_status`). Add `from app.core import fixtures` at module top.

- [ ] **Step 3: Same treatment for Razorpay**

In `backend/app/core/payments.py`, `RazorpayService.__init__`:
```python
        self.use_fixtures = settings.use_fixtures or not (key_id and key_secret)
        self.client = None if self.use_fixtures else razorpay.Client(auth=(key_id, key_secret))
```
Guard `create_order`, `create_upi_intent_order`, `capture_payment`, and `get_payment_details` with the corresponding fixture calls.

- [ ] **Step 4: Verify both modes, commit**

```bash
pytest tests/ -v
git add backend/app/core/fixtures.py backend/app/core/sarvam.py backend/app/core/payments.py
git commit -m "feat: add fixture mode for Sarvam and Razorpay"
```

## Task 6: Boot the stack

- [ ] **Step 1: Start dependencies and backend**

```bash
docker-compose up -d --build
```

- [ ] **Step 2: Wait for health**

```bash
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok","service":"Sangam",...}`

- [ ] **Step 3: If the backend container fails, capture why**

```bash
docker-compose logs sangam-backend --tail 60
```
Most likely causes: missing Alembic migration for new tables (run `alembic upgrade head` inside the container), or an import error from Task 5 edits.

- [ ] **Step 4: Commit any Dockerfile/compose fixes**

```bash
git add -A && git commit -m "chore: get backend booting under docker-compose"
```

---

# SLICE 1 — Vendor/COA domain + Sarvam pipeline

## Task 7: Vendor and licence models

**Files:**
- Create: `backend/app/models/vendor.py`, `backend/app/models/document.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the models**

`backend/app/models/vendor.py` — follow the existing `Workflow` model conventions (UUID PK, `Mapped[]` annotations, `SAEnum`):

```python
from __future__ import annotations
import uuid
from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from sqlalchemy import String, DateTime, Date, Enum as SAEnum, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class VendorStatus(str, Enum):
    DRAFT = "draft"
    PENDING_QUALIFICATION = "pending_qualification"
    QUALIFIED = "qualified"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class LicenceType(str, Enum):
    CDSCO = "cdsco"
    STATE_FDA = "state_fda"
    GST = "gst"
    MCA = "mca"
    ISO = "iso"
    WHO_GMP = "who_gmp"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[VendorStatus] = mapped_column(
        SAEnum(VendorStatus), nullable=False, default=VendorStatus.DRAFT
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    licences = relationship("VendorLicence", back_populates="vendor", lazy="selectin")
    documents = relationship("ExtractedDocument", back_populates="vendor", lazy="selectin")

    @property
    def has_expired_licence(self) -> bool:
        today = date.today()
        return any(lic.expiry_date and lic.expiry_date < today for lic in self.licences)


class VendorLicence(Base):
    __tablename__ = "vendor_licences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    licence_type: Mapped[LicenceType] = mapped_column(SAEnum(LicenceType), nullable=False)
    licence_number: Mapped[str] = mapped_column(String(128), nullable=False)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="licences")
```

`backend/app/models/document.py`:
```python
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text, JSON, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ExtractedDocument(Base):
    __tablename__ = "extracted_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="licence")
    sarvam_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus), nullable=False, default=ExtractionStatus.PENDING
    )
    raw_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    min_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="documents")
```

- [ ] **Step 2: Register in `backend/app/models/__init__.py`**

Follow the existing import style so `Base.metadata` sees the tables:
```python
from app.models.vendor import Vendor, VendorLicence, VendorStatus, LicenceType
from app.models.document import ExtractedDocument, ExtractionStatus
```

- [ ] **Step 3: Verify tables create**

```bash
pytest tests/ -v
```
Expected: PASS — `conftest.py` runs `Base.metadata.create_all`, so failures here mean a model definition error.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add vendor, licence, and extracted-document models"
```

## Task 8: Document intelligence pipeline

**Files:**
- Create: `backend/app/core/document_intelligence.py`, `backend/tests/test_document_intelligence.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.core.document_intelligence import DocumentIntelligence, CONFIDENCE_REVIEW_THRESHOLD


@pytest.mark.asyncio
async def test_extract_licence_from_fixture(db_session):
    di = DocumentIntelligence(db_session)
    doc = await di.extract(
        file_bytes=b"%PDF-1.4 fake", filename="licence.pdf",
        document_type="licence", vendor_id=None,
    )
    assert doc.status.value in ("completed", "needs_review")
    assert doc.structured_data is not None
    assert doc.structured_data["licence_number"] == "MFG/25/2024/KA/00847"
    assert doc.structured_data["vendor_name"] == "Meridian Life Sciences Private Limited"


@pytest.mark.asyncio
async def test_low_confidence_flags_review(db_session):
    di = DocumentIntelligence(db_session)
    flagged = di._compute_review_flag({"a": 0.99, "b": CONFIDENCE_REVIEW_THRESHOLD - 0.01})
    assert flagged is True
    assert di._compute_review_flag({"a": 0.99, "b": 0.98}) is False


@pytest.mark.asyncio
async def test_extraction_failure_degrades_to_review_not_crash(db_session, monkeypatch):
    di = DocumentIntelligence(db_session)

    async def boom(*a, **k):
        raise RuntimeError("Sarvam unavailable")

    monkeypatch.setattr(di.sarvam, "vision_extract", boom)
    doc = await di.extract(
        file_bytes=b"x", filename="licence.pdf", document_type="licence", vendor_id=None,
    )
    assert doc.status.value == "failed"
    assert doc.needs_review is True
    assert "Sarvam unavailable" in (doc.error_message or "")
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_document_intelligence.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`backend/app/core/document_intelligence.py`:
```python
"""Chains Sarvam doc-digitisation and LLM structuring into typed vendor data.

Failure policy: extraction problems produce a NEEDS_REVIEW/FAILED document
with needs_review=True, never an unhandled exception. A vendor onboarding
flow must degrade to human review, not to a 500.
"""
from __future__ import annotations
import json
import uuid
import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sarvam import SarvamAI
from app.models.document import ExtractedDocument, ExtractionStatus

logger = logging.getLogger("sangam.document_intelligence")

CONFIDENCE_REVIEW_THRESHOLD = 0.85
POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 30

EXTRACTION_PROMPT = """You are extracting structured data from an Indian pharmaceutical regulatory document.

Return ONLY valid JSON. No markdown fences, no commentary.

Schema:
{
  "licence_number": string,
  "vendor_name": string,
  "address": string,
  "issuing_authority": string,
  "issue_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "licence_type": "CDSCO" | "STATE_FDA" | "GST" | "MCA" | "ISO" | "WHO_GMP",
  "categories": [string],
  "confidence": { "<field_name>": 0.0-1.0 }
}

Use null for any field not present in the document. Confidence reflects how
clearly each value appears in the source text."""


class DocumentIntelligence:
    def __init__(self, session: AsyncSession, sarvam: Optional[SarvamAI] = None):
        self.session = session
        self.sarvam = sarvam or SarvamAI()

    def _compute_review_flag(self, confidence: Dict[str, float]) -> bool:
        if not confidence:
            return True
        return min(confidence.values()) < CONFIDENCE_REVIEW_THRESHOLD

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        document_type: str = "licence",
        vendor_id: Optional[UUID] = None,
        language_code: str = "en-IN",
    ) -> ExtractedDocument:
        doc = ExtractedDocument(
            id=uuid.uuid4(), vendor_id=vendor_id, filename=filename,
            document_type=document_type, status=ExtractionStatus.PROCESSING,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)

        try:
            job = await self.sarvam.vision_extract(
                document_data=file_bytes, filename=filename, language_code=language_code,
            )
            doc.sarvam_job_id = job.job_id

            markdown = await self._poll_for_output(job.job_id)
            doc.raw_markdown = markdown

            structured = await self._structure(markdown)
            doc.structured_data = structured

            confidence = structured.get("confidence", {}) or {}
            doc.min_confidence = min(confidence.values()) if confidence else None
            doc.needs_review = self._compute_review_flag(confidence)
            doc.status = (
                ExtractionStatus.NEEDS_REVIEW if doc.needs_review else ExtractionStatus.COMPLETED
            )
        except Exception as exc:
            logger.exception("Document extraction failed for %s", filename)
            doc.status = ExtractionStatus.FAILED
            doc.needs_review = True
            doc.error_message = str(exc)

        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def _poll_for_output(self, job_id: str) -> str:
        for _ in range(MAX_POLL_ATTEMPTS):
            status = await self.sarvam.vision_job_status(job_id)
            state = (status.get("status") or "").lower()
            if state in ("completed", "succeeded", "done"):
                return status.get("output") or status.get("output_text") or ""
            if state in ("failed", "error"):
                raise RuntimeError(f"Sarvam digitisation job {job_id} failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        raise TimeoutError(f"Sarvam job {job_id} did not complete in time")

    async def _structure(self, markdown: str) -> Dict[str, Any]:
        result = await self.sarvam.llm_complete(
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": markdown},
            ],
            temperature=0.1,
        )
        return self._parse_json(result.content)

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned non-JSON output: {exc}") from exc
```

- [ ] **Step 4: Make fixture LLM return the licence JSON**

In `backend/app/core/sarvam.py`'s `llm_complete` fixture guard, return `fixtures.EXTRACTED_LICENCE_JSON` serialised, so the pipeline parses real structure:
```python
        if self.use_fixtures:
            data = fixtures.sarvam_llm(json.dumps(fixtures.EXTRACTED_LICENCE_JSON))
            return SarvamLLMResult(
                content=data["choices"][0]["message"]["content"], model=model,
            )
```
Add `import json` at module top.

- [ ] **Step 5: Confirm pass, commit**

```bash
pytest tests/test_document_intelligence.py -v
git add backend/app/core/document_intelligence.py backend/app/core/sarvam.py backend/tests/test_document_intelligence.py
git commit -m "feat: add Sarvam document intelligence extraction pipeline"
```

## Task 9: Vendor API

**Files:**
- Create: `backend/app/api/vendors.py`, `backend/app/schemas/vendor.py`, `backend/tests/test_vendor_api.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest


@pytest.mark.asyncio
async def test_create_and_list_vendor(client, auth_headers):
    resp = await client.post("/vendors", json={
        "name": "Meridian Life Sciences", "gstin": "29AABCM1234K1Z5",
        "contact_email": "qa@meridian.example",
    }, headers=auth_headers)
    assert resp.status_code == 201
    vendor_id = resp.json()["id"]

    listing = await client.get("/vendors", headers=auth_headers)
    assert listing.status_code == 200
    assert any(v["id"] == vendor_id for v in listing.json())


@pytest.mark.asyncio
async def test_upload_document_extracts_licence(client, auth_headers):
    created = await client.post(
        "/vendors", json={"name": "Meridian Life Sciences"}, headers=auth_headers,
    )
    vendor_id = created.json()["id"]

    resp = await client.post(
        f"/vendors/{vendor_id}/documents",
        files={"file": ("licence.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"document_type": "licence"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["structured_data"]["licence_number"] == "MFG/25/2024/KA/00847"
```

- [ ] **Step 2: Add an `auth_headers` fixture to `backend/tests/conftest.py`**

Inspect `app/api/dependencies.py::get_current_actor` first, then override it the same way `get_session` is overridden, so tests do not depend on real JWT issuance:
```python
@pytest_asyncio.fixture
async def auth_headers(db_session):
    import uuid
    from app.api.dependencies import get_current_actor
    from app.models.actor import Actor, ActorType

    actor = Actor(id=uuid.uuid4(), name="Test QA Head", actor_type=ActorType.HUMAN)
    db_session.add(actor)
    await db_session.commit()

    async def override_actor():
        return actor

    app.dependency_overrides[get_current_actor] = override_actor
    return {"X-Test-Actor": str(actor.id)}
```
If `Actor` requires additional non-nullable columns, add them here — check `app/models/actor.py` before writing.

- [ ] **Step 3: Run, confirm failure**

Run: `pytest tests/test_vendor_api.py -v`
Expected: FAIL — 404, router not registered.

- [ ] **Step 4: Write schemas and router**

`backend/app/schemas/vendor.py`:
```python
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class VendorCreate(BaseModel):
    name: str
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class LicenceOut(BaseModel):
    id: UUID
    licence_type: str
    licence_number: str
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    verified: bool
    extraction_confidence: Optional[float] = None


class VendorOut(BaseModel):
    id: UUID
    name: str
    gstin: Optional[str] = None
    address: Optional[str] = None
    status: str
    created_at: datetime
    licences: List[LicenceOut] = []


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    document_type: str
    status: str
    structured_data: Optional[Dict[str, Any]] = None
    min_confidence: Optional[float] = None
    needs_review: bool
    error_message: Optional[str] = None
```

`backend/app/api/vendors.py` — routes: `POST /vendors`, `GET /vendors`, `GET /vendors/{id}`, `POST /vendors/{id}/documents`, `POST /vendors/{id}/submit-for-qualification`. Follow the dependency and error-handling style already used in `app/api/payments.py`. On document upload, call `DocumentIntelligence.extract`, and when a licence is extracted with sufficient confidence, create the matching `VendorLicence` row. `submit-for-qualification` sets status to `PENDING_QUALIFICATION` and creates a `Workflow` in the `APPROVAL` phase with the vendor id in `extra_attributes`.

- [ ] **Step 5: Register the router in `backend/app/main.py`**

```python
from app.api.vendors import router as vendors_router
app.include_router(vendors_router)
```

- [ ] **Step 6: Confirm pass, commit**

```bash
pytest tests/test_vendor_api.py -v
git add backend/app/api/vendors.py backend/app/schemas/vendor.py backend/app/main.py backend/tests/
git commit -m "feat: add vendor API with document extraction"
```

---

# SLICE 2 — Razorpay lifecycle

## Task 10: Event-driven escrow release

`release_escrow` exists but no caller invokes it.

**Files:**
- Modify: `backend/app/core/coordinator.py` (`verify_handoff`)
- Create: `backend/tests/test_escrow_release.py`

- [ ] **Step 1: Write the failing test**

```python
import uuid
import pytest
from app.core.coordinator import Coordinator
from app.models.payment import Escrow, EscrowStatus, Payment, PaymentStatus


@pytest.mark.asyncio
async def test_handoff_verification_releases_escrow(db_session, sample_workflow, sample_actors):
    payment = Payment(
        id=uuid.uuid4(), workflow_id=sample_workflow.id, amount=250000.0,
        currency="INR", status=PaymentStatus.CAPTURED,
        razorpay_payment_id="pay_FIXTURE00001",
    )
    escrow = Escrow(
        id=uuid.uuid4(), workflow_id=sample_workflow.id, payment_id=payment.id,
        amount=250000.0, status=EscrowStatus.HELD, release_condition="delivery_verified",
    )
    db_session.add_all([payment, escrow])
    await db_session.commit()

    coord = Coordinator(db_session)
    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id, to_actor_id=sample_actors[1].id,
        artifact="COA-4471.pdf", artifact_type="coa",
    )
    await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)

    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.RELEASED
    assert escrow.released_at is not None
```

Add `sample_workflow` and `sample_actors` fixtures to `conftest.py` creating one `Workflow` and two `Actor` rows.

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_escrow_release.py -v`
Expected: FAIL — escrow still `HELD`.

- [ ] **Step 3: Extend `verify_handoff`**

Append to `Coordinator.verify_handoff` in `backend/app/core/coordinator.py`, before returning:

```python
        await self._maybe_release_escrow(handoff)
        return handoff

    async def _maybe_release_escrow(self, handoff: Handoff) -> None:
        """Release any held escrow whose condition is satisfied by this handoff.

        Escrow release must never break handoff verification: a payment-gateway
        failure is logged and left for retry, not raised to the caller.
        """
        from app.models.payment import Escrow, EscrowStatus
        from app.core.payments import PaymentManager

        result = await self.session.execute(
            select(Escrow).where(
                Escrow.workflow_id == handoff.workflow_id,
                Escrow.status == EscrowStatus.HELD,
            )
        )
        escrows = result.scalars().all()
        if not escrows:
            return

        context = {
            "delivery_verified": True,
            "artifact_type": handoff.artifact_type or "",
            "artifact": handoff.artifact or "",
        }
        manager = PaymentManager(self.session)

        for escrow in escrows:
            if not ConditionEvaluator(context).evaluate(escrow.release_condition or ""):
                continue
            try:
                await manager.release_escrow(
                    escrow.id, release_trigger=f"handoff_verified:{handoff.id}",
                )
            except Exception:
                logger.exception("Escrow %s release failed after handoff %s", escrow.id, handoff.id)
```

Add at module top:
```python
import logging
logger = logging.getLogger("sangam.coordinator")
```

- [ ] **Step 4: Confirm pass, commit**

```bash
pytest tests/test_escrow_release.py -v
git add backend/app/core/coordinator.py backend/tests/
git commit -m "feat: release escrow automatically on handoff verification"
```

---

# SLICE 3 — Android and evidence capture

## Task 11: Vendor screens

**Files:**
- Create: `android/app/src/main/java/com/sangam/app/ui/screens/VendorListScreen.kt`, `VendorDetailScreen.kt`, `AddVendorScreen.kt`
- Modify: `android/app/src/main/java/com/sangam/app/network/ApiService.kt`, `ui/navigation/SangamNavHost.kt`

- [ ] **Step 1: Read the existing patterns first**

```bash
cat android/app/src/main/java/com/sangam/app/network/ApiService.kt
cat android/app/src/main/java/com/sangam/app/ui/screens/WorkflowListScreen.kt
cat android/app/src/main/java/com/sangam/app/ui/navigation/SangamNavHost.kt
```
Match the existing Retrofit interface style, Compose screen signature, and nav-route registration exactly. Do not introduce a second HTTP client or a different state pattern.

- [ ] **Step 2: Add vendor endpoints to `ApiService.kt`**

Mirror the existing annotation style:
```kotlin
    @GET("vendors")
    suspend fun listVendors(): List<VendorDto>

    @GET("vendors/{id}")
    suspend fun getVendor(@Path("id") id: String): VendorDto

    @POST("vendors")
    suspend fun createVendor(@Body body: CreateVendorRequest): VendorDto

    @Multipart
    @POST("vendors/{id}/documents")
    suspend fun uploadVendorDocument(
        @Path("id") id: String,
        @Part file: MultipartBody.Part,
        @Part("document_type") documentType: RequestBody,
    ): ExtractedDocumentDto
```
Define `VendorDto`, `CreateVendorRequest`, and `ExtractedDocumentDto` alongside the existing DTOs.

- [ ] **Step 3: Build the three screens**

`VendorListScreen` — `LazyColumn` of vendor cards showing name, status chip, and licence-expiry warning. `AddVendorScreen` — name/GSTIN fields plus a document-pick button that uploads and then renders the extracted fields with confidence indicators, flagging any `needs_review` field for manual confirmation. `VendorDetailScreen` — vendor header, licence list, and a **Submit for Qualification** action.

- [ ] **Step 4: Register routes in `SangamNavHost.kt`**

Add `vendors`, `vendors/add`, and `vendors/{id}` composable destinations following the existing registration pattern.

- [ ] **Step 5: Build**

```bash
cd android && ./gradlew assembleDebug
```
Expected: `BUILD SUCCESSFUL`. Compose compiler errors here are usually a Material3 import mismatch — check against `WorkflowListScreen.kt`.

- [ ] **Step 6: Commit**

```bash
git add android/
git commit -m "feat: add vendor screens to Android app"
```

## Task 12: Run on the emulator and capture evidence

**Files:**
- Create: `docs/demo/screenshots/` (output directory)

- [ ] **Step 1: Boot the emulator**

```bash
"$ANDROID_HOME/emulator/emulator.exe" -avd star_trail_emu -no-snapshot-load &
"$ANDROID_HOME/platform-tools/adb.exe" wait-for-device
"$ANDROID_HOME/platform-tools/adb.exe" shell getprop sys.boot_completed
```
Expected: eventually prints `1`.

- [ ] **Step 2: Confirm the emulator reaches the backend**

The app uses `http://10.0.2.2:8000`, the emulator alias for host localhost. Verify the backend is up on the host first:
```bash
curl -s http://localhost:8000/health
```

- [ ] **Step 3: Install and launch**

```bash
"$ANDROID_HOME/platform-tools/adb.exe" install -r android/app/build/outputs/apk/debug/app-debug.apk
"$ANDROID_HOME/platform-tools/adb.exe" shell am start -n com.sangam.app/.MainActivity
```

- [ ] **Step 4: Capture each demo step**

```bash
"$ANDROID_HOME/platform-tools/adb.exe" exec-out screencap -p > docs/demo/screenshots/01-login.png
```
Repeat through the flow: vendor list, add vendor, document upload, extracted fields, qualification workflow, approval, payment, confirmation.

- [ ] **Step 5: Commit the evidence**

```bash
git add docs/demo/
git commit -m "docs: capture one-phone demo screenshots"
```

## Task 13: VC-facing outcome document

**Files:**
- Create: `docs/demo/DEMO_RESULTS.md`

- [ ] **Step 1: Write it honestly**

Document what runs end to end, with embedded screenshots; which capabilities are live versus fixture-backed; measured latency against the 100ms p99 target; the security issues found and fixed (unauthenticated webhook, `eval()` injection, duplicate routes); and a clear "not yet built" section. A VC will discover gaps anyway — finding them listed by the founder reads as rigour, finding them hidden reads as a red flag.

- [ ] **Step 2: Commit**

```bash
git add docs/demo/DEMO_RESULTS.md
git commit -m "docs: add demo results summary"
```

---

## Self-Review Notes

**Spec coverage:** §3 Slice 0 → Tasks 1-6. §3 Slice 1 → Tasks 7-9. §3 Slice 2 → Task 10. §3 Slice 3 → Tasks 11-12. §4 fixture mode → Task 5. §5 error handling → Task 8 failure policy, Task 10 escrow isolation. §6 testing → tests in Tasks 2,3,4,8,9,10. §7 out-of-scope respected: no ESP32, no RazorpayX, no web rework.

**Known deviations:** §5's p99 latency assertion is measured and reported in Task 13 rather than gated in CI — enforcing a 100ms budget as a failing test on an unprofiled codebase would likely block the demo on unrelated slowness. Measure first, gate once a baseline exists.

**Type consistency:** `VendorStatus`/`LicenceType`/`ExtractionStatus` used identically in models, schemas, and tests. `safe_evaluate(condition, context) -> bool` and `_compute_review_flag(confidence) -> bool` match across definition and call sites. `CONFIDENCE_REVIEW_THRESHOLD` defined once in `document_intelligence.py`, imported by tests.
