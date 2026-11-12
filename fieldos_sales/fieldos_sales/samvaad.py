"""Calls through Sarvam Voice Agents (Samvaad) instead of our own Exotel voice loop.

Samvaad hosts the whole call (number, speech, the agent's brain). We only:
- find the deployment (by name or number, default "sangam") to get its agent, version and line,
- place one instant outbound call per prospect, passing that firm's notes as agent variables,
- take Samvaad's webhook after the call and log the transcript and outcome like any other call.

The agent's instruction lives in the Samvaad dashboard: paste SAMVAAD_AGENT.md there. It has no
pricing in it, so the agent has none to reveal; every variable we send passes the pricing filter,
and the transcript is checked again afterwards (a slip is logged as a pricing_alert).

Every call still goes through `can_contact` (live mode, approval, DND, hours, caps) unless it is
a self-test number. The Voice Agents key is separate from the normal Sarvam key: SARVAM_SAMVAAD_API_KEY.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings
from .conversation import Conversation
from .guardrails import check_outbound, is_opt_out, pricing_violation
from .store import Store

log = logging.getLogger("fieldos_sales.samvaad")

BASE = "https://apps.sarvam.ai/api"
LANGUAGES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada", "mr": "Marathi"}
# Output variables we ask the Samvaad agent to fill (see SAMVAAD_AGENT.md) -> our outcomes.
OUTCOMES = {"demo_booked", "callback_later", "send_info", "not_now", "opted_out", "handover", "ended"}


class SamvaadError(RuntimeError):
    pass


def _mask(phone: str) -> str:
    return phone[:3] + "*" * max(0, len(phone) - 7) + phone[-4:] if len(phone) > 7 else "****"


class SamvaadDialer:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.s = settings
        self.client = client
        self._line: dict[str, Any] | None = None

    def configured(self) -> list[str]:
        return [n for n, v in (("SARVAM_SAMVAAD_API_KEY", self.s.samvaad_api_key),
                               ("SAMVAAD_ORG_ID", self.s.samvaad_org_id),
                               ("SAMVAAD_WORKSPACE_ID", self.s.samvaad_workspace_id)) if not v]

    def _request(self, method: str, url: str, **kw) -> Any:
        missing = self.configured()
        if missing:
            raise SamvaadError("Samvaad not configured: " + ", ".join(missing))
        client = self.client or httpx.Client(timeout=30)
        try:
            r = client.request(method, url, headers={"X-API-Key": self.s.samvaad_api_key}, **kw)
            if r.status_code >= 400:
                raise SamvaadError(f"Samvaad {r.status_code}: {r.text[:300]}")
            return r.json()
        finally:
            if self.client is None:
                client.close()

    def _scope(self) -> str:
        return f"orgs/{self.s.samvaad_org_id}/workspaces/{self.s.samvaad_workspace_id}"

    def deployments(self) -> list[dict[str, Any]]:
        out, offset = [], 0
        while True:
            page = self._request("GET", f"{BASE}/app-authoring/v1/{self._scope()}/deployments",
                                 params={"offset": offset, "limit": 100})
            out += page.get("items", [])
            offset += len(page.get("items", []))
            if not page.get("next_page_uri") or not page.get("items"):
                return out

    def line(self) -> dict[str, Any]:
        """The agent + phone line to call from: the deployment named (or numbered) SAMVAAD_DEPLOYMENT."""
        if self._line:
            return self._line
        want = self.s.samvaad_deployment.lower().strip()
        found = [d for d in self.deployments()
                 if d.get("channel_direction") in ("outbound", "inbound_outbound")
                 and (want in (d.get("name") or "").lower() or want in (d.get("app_id") or "").lower()
                      or any(want.lstrip("+") in n for n in d.get("phone_numbers", [])))]
        if not found:
            raise SamvaadError(f"no outbound deployment matching '{self.s.samvaad_deployment}' "
                               "(set SAMVAAD_DEPLOYMENT to its name, agent id or number)")
        dep = found[0]
        if dep.get("status") == "paused":
            raise SamvaadError(f"deployment '{dep.get('name')}' is paused in Samvaad")
        full = self._request("GET", f"{BASE}/app-authoring/v1/{self._scope()}/deployments/{dep['deployment_id']}")
        conns = full.get("connection_configs") or []
        if not conns:
            raise SamvaadError(f"deployment '{dep.get('name')}' has no phone line")
        self._line = {"app_id": full["app_id"], "app_version": full["app_version"], "name": full.get("name"),
                      "connection_id": conns[0]["connection_id"], "agent_phone_number": conns[0]["agent_phone_number"]}
        return self._line

    def dial(self, phone: str, prospect_id: int, variables: dict[str, Any] | None = None,
             opening: str = "", language: str = "en") -> str:
        """Place one call. Returns Samvaad's attempt_id (stored as the call's call_sid)."""
        line = self.line()
        overrides: dict[str, Any] = {"initial_language_name": LANGUAGES.get(language, "English")}
        if opening:
            overrides["initial_bot_message"] = opening
        body: dict[str, Any] = {
            "app_config": {"app_id": line["app_id"], "app_version": line["app_version"],
                           "connection_config": {"connection_id": line["connection_id"],
                                                 "agent_phone_number": line["agent_phone_number"]},
                           "agent_variables": variables or {}, "app_overrides": overrides},
            "user_config": {"user_phone_number": phone},
        }
        if self.s.public_base_url and self.s.voice_stream_token:
            body["webhook_config"] = {"url": f"{self.s.public_base_url}/samvaad/webhook?token={self.s.voice_stream_token}",
                                      "metadata": {"prospect_id": prospect_id}}
        return self._request("POST", f"{BASE}/outbounds/v1/{self._scope()}/outbounds", json=body)["attempt_id"]


def call_inputs(store: Store, settings: Settings, prospect: dict[str, Any], phone: str) -> tuple[dict[str, Any], str, str]:
    """(agent_variables, opening line, language) for one firm. Raises if anything would mention pricing."""
    convo = Conversation.load(store, None, prospect, phone, "call",  # type: ignore[arg-type]
                              agent_name=settings.agent_name, agent_gender=settings.agent_gender)
    p = convo.profile
    fits = "; ".join(f"{f.get('pain')}: {f.get('feature')} ({f.get('why')})" for f in p.get("fieldos_fits", [])[:3])
    variables = {
        "agent_name": settings.agent_name,
        "firm_name": prospect["firm"],
        "contact_name": prospect.get("contact_name") or "",
        "segment": prospect.get("segment") or "",
        "about_firm": (p.get("summary") or "")[:600],
        "projects": ", ".join(p.get("project_types", [])[:4]),
        "locations": ", ".join(p.get("locations", [])[:4]),
        "likely_pains": "; ".join(p.get("likely_pains", [])[:4]),
        "fieldos_fits": fits[:700],
        "opening_hook": p.get("opening_hook") or "",
        "decision_maker": p.get("decision_maker_hint") or "",
        "call_brief": (convo.brief or "")[:1500],
    }
    opening = convo.opening()
    for text in (opening, *map(str, variables.values())):
        problems = check_outbound(text)
        if problems:
            raise SamvaadError("call notes fail the outbound check: " + "; ".join(problems))
    return variables, opening, convo.language


def make_dial(store: Store, settings: Settings, dialer: SamvaadDialer | None = None):
    """A `dial(phone, prospect_id) -> attempt_id` for the scheduler and the `call` command."""
    dialer = dialer or SamvaadDialer(settings)

    def dial(phone: str, prospect_id: int) -> str:
        prospect = store.prospect(prospect_id)
        if not prospect:
            raise SamvaadError(f"no prospect {prospect_id}")
        variables, opening, language = call_inputs(store, settings, prospect, phone)
        return dialer.dial(phone, prospect_id, variables, opening, language)
    return dial


def handle_webhook(store: Store, payload: dict[str, Any]) -> dict[str, Any]:
    """Log a finished Samvaad call: status, transcript, outcome; honour opt-outs; flag pricing slips."""
    attempt = str(payload.get("attempt_id") or "")
    row = store.one("SELECT * FROM calls WHERE call_sid = ?", (attempt,))
    if not row:
        return {"ok": False, "reason": "unknown attempt"}
    pid, phone = row["prospect_id"], row["phone"]
    status = str(payload.get("status") or "unknown")
    store.execute("UPDATE calls SET status = ? WHERE call_sid = ?", ({"connected": "completed"}.get(status, status), attempt))
    turns = payload.get("interaction_transcript") or []
    if status != "connected" or not turns:
        store.log("call", "event", prospect_id=pid, phone=phone, outcome=f"status:{status}",
                  meta={"call_sid": attempt, "failure_reason": payload.get("failure_reason"), "provider": "samvaad"})
        return {"ok": True, "logged": "status"}
    out_vars = payload.get("final_agent_variables") or {}
    lines = [("AI: " if t.get("role") == "agent" else "Prospect: ") + str(t.get("en_text", "")) for t in turns]
    user_turns = [t for t in turns if t.get("role") != "agent"]
    outcome = str(out_vars.get("call_outcome") or "").strip().lower()
    opted_out = outcome == "opted_out" or any(is_opt_out(str(t.get("en_text", ""))) for t in user_turns)
    if opted_out:
        outcome = "opted_out"
        store.suppress(phone, "asked to stop on a Samvaad call", "samvaad")
    if outcome not in OUTCOMES:
        outcome = "ended"
    slips = [v for t in turns if t.get("role") == "agent" for v in [pricing_violation(str(t.get("en_text", "")))] if v]
    meta = {"call_sid": attempt, "provider": "samvaad", "duration_s": payload.get("duration"),
            "prospect_turns": len(user_turns), "interaction_id": payload.get("interaction_id"),
            "language": str(out_vars.get("language") or ""), "ended_by": "agent" if outcome != "ended" else "caller",
            "price_asks": sum("price" in str(t.get("en_text", "")).lower() or "cost" in str(t.get("en_text", "")).lower()
                              for t in user_turns)}
    tid = store.log("call", "transcript", prospect_id=pid, phone=phone, text="\n".join(lines), outcome=outcome, meta=meta)
    if outcome not in ("ended",):
        store.log("call", "event", prospect_id=pid, phone=phone, outcome=outcome,
                  meta={"note": str(out_vars.get("note") or ""), "demo_slot": str(out_vars.get("demo_slot") or ""),
                        "callback_time": str(out_vars.get("callback_time") or ""), "call_sid": attempt})
    if slips:
        log.error("PRICING SLIP on Samvaad call %s (prospect %s): %s", attempt, pid, slips)
        store.log("call", "event", prospect_id=pid, phone=phone, outcome="pricing_alert",
                  meta={"call_sid": attempt, "matched": slips[:5]})
    return {"ok": True, "logged": "transcript", "touch_id": tid, "outcome": outcome}


def describe(dialer: SamvaadDialer) -> list[str]:
    """Safe-to-print summary of the workspace's deployments (numbers masked)."""
    lines = []
    for d in dialer.deployments():
        nums = ", ".join(_mask(n) for n in d.get("phone_numbers", []))
        lines.append(f"{d.get('name') or '-'}  agent={d.get('app_id')} v{d.get('app_version')}  "
                     f"{d.get('channel_direction')}  {d.get('status') or ''}  numbers: {nums}")
    return lines
