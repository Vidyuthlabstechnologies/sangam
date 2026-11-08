"""Drive the full one-phone demo flow against a running backend.

Exercises every investor-mandated capability in one narrative and reports
per-step latency, so the numbers in the demo write-up are measured rather
than claimed.

Usage:
    python -m scripts.demo_flow            # against http://localhost:8000
    python -m scripts.demo_flow --url ...
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

SAMPLE_PDF = Path(__file__).resolve().parents[2] / "docs" / "demo" / "sample_cdsco_licence.pdf"


def load_licence_pdf() -> bytes:
    """Load the synthetic CDSCO licence, generating it if absent."""
    if not SAMPLE_PDF.exists():
        from scripts.make_sample_licence import build
        build(SAMPLE_PDF)
    return SAMPLE_PDF.read_bytes()


results: List[Dict[str, Any]] = []


def record(step: str, ms: float, ok: bool, detail: str = "") -> None:
    results.append({"step": step, "ms": round(ms, 1), "ok": ok, "detail": detail})
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {step:<42} {ms:7.1f} ms  {detail}")


async def timed(step: str, coro, extract=lambda r: ""):
    start = time.perf_counter()
    try:
        resp = await coro
        ms = (time.perf_counter() - start) * 1000
        ok = resp.status_code < 400
        detail = extract(resp) if ok else f"HTTP {resp.status_code}: {resp.text[:120]}"
        record(step, ms, ok, detail)
        return resp if ok else None
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        record(step, ms, False, f"{type(exc).__name__}: {exc}")
        return None


async def main(base_url: str) -> int:
    print(f"\nSangam one-phone demo flow  ->  {base_url}\n" + "=" * 78)

    async with httpx.AsyncClient(base_url=base_url, timeout=180) as c:
        # 1 - the access token is issued by Zitadel (authorization code + PKCE).
        access_token = os.environ.get("SANGAM_ACCESS_TOKEN", "").strip()
        if not access_token:
            print("\nSet SANGAM_ACCESS_TOKEN to a Zitadel access token. Sangam does not take a password.")
            return 1
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = await timed(
            "1. Authenticate (Zitadel access token)",
            c.get("/auth/me", headers=headers),
            lambda r: r.json()["name"],
        )
        if not resp:
            print("\nCannot continue without a valid Zitadel access token.")
            return 1

        # 2 - register vendor
        resp = await timed(
            "2. Create vendor",
            c.post("/vendors", json={
                "name": "Meridian Life Sciences",
                "gstin": "29AABCM1234K1Z5",
                "contact_email": "qa@meridian.example",
            }, headers=headers),
            lambda r: r.json()["name"],
        )
        if not resp:
            return 1
        vendor_id = resp.json()["id"]

        # 3 - Sarvam document intelligence
        resp = await timed(
            "3. Upload licence -> Sarvam extraction",
            c.post(
                f"/vendors/{vendor_id}/documents",
                files={"file": ("cdsco_licence.pdf", load_licence_pdf(), "application/pdf")},
                data={"document_type": "licence"},
                headers=headers,
            ),
            lambda r: f"status={r.json()['status']} conf={r.json().get('min_confidence')}",
        )
        extracted = resp.json() if resp else {}
        if extracted.get("structured_data"):
            sd = extracted["structured_data"]
            print(f"        extracted licence : {sd.get('licence_number')}")
            print(f"        extracted vendor  : {sd.get('vendor_name')}")
            print(f"        expiry            : {sd.get('expiry_date')}")

        # 4 - human review gate. Low-confidence extractions are deliberately
        #     NOT auto-promoted to a licence; a reviewer confirms them.
        doc_id = extracted.get("id")
        if extracted.get("needs_review") and doc_id:
            print(f"        confidence {extracted.get('min_confidence')} < threshold"
                  f" -> flagged for review (working as designed)")
            await timed(
                "4. QA reviewer confirms extraction",
                c.post(f"/vendors/{vendor_id}/documents/{doc_id}/confirm", headers=headers),
                lambda r: f"{len(r.json()['licences'])} licence(s) now verified",
            )
        else:
            await timed(
                "4. Vendor shows extracted licence",
                c.get(f"/vendors/{vendor_id}", headers=headers),
                lambda r: f"{len(r.json()['licences'])} licence(s)",
            )

        # 5 - qualification workflow
        resp = await timed(
            "5. Submit for qualification",
            c.post(f"/vendors/{vendor_id}/submit-for-qualification", headers=headers),
            lambda r: r.json()["status"],
        )
        workflow_id = resp.json()["workflow_id"] if resp else None

        # 6 - Sarvam voice round-trip: synthesise Hindi, then transcribe it.
        #     Using generated speech as STT input proves both directions of
        #     the vernacular pipeline with one real audio payload.
        approval_phrase = "मैं इस विक्रेता को मंजूरी देता हूं"
        resp = await timed(
            "6. Synthesise Hindi approval (Sarvam TTS)",
            c.post("/ai/text-to-speech", json={
                "text": approval_phrase,
                "target_language_code": "hi-IN",
                "speaker": "anushka",
            }, headers=headers),
            lambda r: f"{len(r.json().get('audio_base64',''))} b64 chars",
        )
        spoken_wav = base64.b64decode(resp.json()["audio_base64"]) if resp else b""

        if spoken_wav:
            resp = await timed(
                "7. Transcribe it back (Sarvam STT hi-IN)",
                c.post(
                    "/ai/speech-to-text",
                    files={"file": ("approval.wav", spoken_wav, "audio/wav")},
                    data={"language_code": "hi-IN"},
                    headers=headers,
                ),
                lambda r: r.json().get("transcript", "")[:50],
            )
            if resp:
                got = resp.json().get("transcript", "")
                print(f"        spoken   : {approval_phrase}")
                print(f"        heard    : {got}")

        # 7 - Razorpay UPI escrow
        payment_id = None
        if workflow_id:
            resp = await timed(
                "8. Initiate UPI advance (Razorpay)",
                c.post("/payments/initiate", json={
                    "workflow_id": workflow_id,
                    "amount": 250000.0,
                    "method": "upi_intent",
                    "description": "Advance against PO-4471",
                }, headers=headers),
                lambda r: r.json()["razorpay_order_id"],
            )
            payment_id = resp.json()["payment_id"] if resp else None

        escrow_id = None
        if workflow_id and payment_id:
            resp = await timed(
                "9. Hold advance in escrow",
                c.post("/payments/escrow", json={
                    "workflow_id": workflow_id,
                    "payment_id": payment_id,
                    "amount": 250000.0,
                    "release_condition": "delivery_verified",
                }, headers=headers),
                lambda r: f"{r.json()['status']} INR {r.json()['amount']:,.0f}",
            )
            escrow_id = resp.json()["id"] if resp else None

        # 9 - Sarvam TTS confirmation
        resp = await timed(
            "10. Spoken settlement confirmation (TTS)",
            c.post("/ai/text-to-speech", json={
                "text": "विक्रेता योग्यता स्वीकृत। अग्रिम राशि एस्क्रो में सुरक्षित है।",
                "target_language_code": "hi-IN",
                "speaker": "anushka",
            }, headers=headers),
            lambda r: f"{len(r.json().get('audio_base64',''))} b64 chars",
        )

        # 10 - compliance early warning
        resp = await timed(
            "11. Licence expiry early-warning",
            c.get("/vendors/expiring?days=90", headers=headers),
            lambda r: f"{len(r.json())} vendor(s) expiring",
        )

    print("=" * 78)
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    api_steps = [r for r in results if r["ok"] and not r["step"].startswith(("3.", "6.", "7.", "10."))]
    if api_steps:
        slowest = max(api_steps, key=lambda r: r["ms"])
        print(f"Internal API p-max: {slowest['ms']:.1f} ms ({slowest['step']})")
    print(f"Result: {passed}/{total} steps passed\n")

    out = Path(__file__).resolve().parents[2] / "docs" / "demo" / "flow_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Timings written to {out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.url)))
