"""Claude calls with a daily spend cap, plus an offline stand-in.

Uses the cheapest Claude model (Haiku) by default. Every call returns JSON
that matches a schema (structured outputs), so callers never parse prose.
With no ANTHROPIC_API_KEY, OfflineLLM returns simple scripted answers so the
whole pipeline can be rehearsed and tested for free.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Protocol

from .config import Settings
from .store import Store

log = logging.getLogger("fieldos_sales.llm")

# US dollars per million tokens. Check https://www.anthropic.com/pricing if you change model.
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}


class BudgetExceeded(RuntimeError):
    pass


class LLM(Protocol):
    def json(self, *, purpose: str, system: list[dict[str, Any]], messages: list[dict[str, Any]],
             schema: dict[str, Any], max_tokens: int = 1024, fast: bool = False) -> dict[str, Any]: ...


class ClaudeLLM:
    def __init__(self, settings: Settings, store: Store, client: Any = None):
        import anthropic

        self.settings = settings
        self.store = store
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=30.0)

    def json(self, *, purpose: str, system: list[dict[str, Any]], messages: list[dict[str, Any]],
             schema: dict[str, Any], max_tokens: int = 1024, fast: bool = False) -> dict[str, Any]:
        if self.store.llm_spend_today() >= self.settings.llm_daily_budget_usd:
            raise BudgetExceeded(f"daily AI budget of ${self.settings.llm_daily_budget_usd:.2f} used up")
        kwargs: dict[str, Any] = {}
        if fast:
            # Live phone calls: answer quickly, no extended reasoning.
            kwargs["thinking"] = {"type": "disabled"}
            kwargs["output_config"] = {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
        else:
            kwargs["output_config"] = {"effort": "medium", "format": {"type": "json_schema", "schema": schema}}
        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            **kwargs,
        )
        usage = response.usage
        in_price, out_price = PRICES.get(self.settings.model, (1.0, 5.0))
        in_tokens = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        usd = in_tokens / 1e6 * in_price + (usage.output_tokens or 0) / 1e6 * out_price
        self.store.add_llm_usage(purpose, in_tokens, usage.output_tokens or 0, usd)
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("model output was cut off (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(text)


class OfflineLLM:
    """Deterministic stand-in. `responder(purpose, messages, schema)` can be injected in tests."""

    def __init__(self, responder: Callable[[str, list, dict], dict] | None = None):
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    def json(self, *, purpose: str, system: list[dict[str, Any]], messages: list[dict[str, Any]],
             schema: dict[str, Any], max_tokens: int = 1024, fast: bool = False) -> dict[str, Any]:
        self.calls.append({"purpose": purpose, "system": system, "messages": messages})
        if self.responder:
            return self.responder(purpose, messages, schema)
        return _offline_answer(purpose, messages)


def _offline_answer(purpose: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    if purpose == "research":
        return {
            "summary": "Researched offline: no AI key set, so this profile only repeats the spreadsheet.",
            "business_type": "unknown", "project_types": [], "locations": [], "scale_signals": [],
            "likely_pains": ["tracking labour, spending and deliveries across sites"],
            "fieldos_fits": [{"pain": "tracking work across sites", "feature": "Daily Site Brief",
                              "why": "one screen shows which site needs attention"}],
            "opening_hook": "",
            "decision_maker_hint": "", "language_hint": "en", "confidence": "low",
            "evidence": [],
        }
    if purpose == "pitch":
        return {
            "call_brief": "Offline draft. Ask how they track attendance, spending and deliveries across sites today, then offer a 30-minute walkthrough.",
            "whatsapp_opener": "Namaste sir, this is the FieldOS team from ML Dynamic Solutions, Hyderabad. How does your team track site attendance and deliveries today: register, Excel or WhatsApp? We built an app for exactly this and would be glad to show you in 30 minutes.",
        }
    if purpose == "insight_summary":
        text = messages[-1]["content"].lower()
        opted = "removed your number" in text or "won't get any more" in text
        booked = "confirm that slot" in text or "walkthrough booked" in text
        return {
            "summary": "Offline summary (no AI key set): read the transcript for details.",
            "interest": "hot" if booked else "none" if opted else "warm",
            "sentiment": "negative" if opted else "neutral", "decision_maker": "unknown",
            "current_method": "unknown", "competitors": [], "pains": [],
            "objections": [], "why_ended": "opted_out" if opted else "booked_demo" if booked else "other",
            "next_step": "", "agent_mistakes": [], "coaching_tip": "",
        }
    if purpose == "insight_learn":
        return {"headline": "Offline review (no AI key set): set ANTHROPIC_API_KEY for real recommendations.",
                "what_works": [], "what_hurts": [], "changes": []}
    turns = sum(1 for m in messages if m["role"] == "user" and not m["content"].startswith("["))
    script = [
        ("Thank you. How many sites are you running right now, and how do your supervisors report attendance and spending from them?", "continue"),
        ("That is exactly where FieldOS helps: supervisors record it on the phone even with no signal, and you see every site's week in one place. Could I show you in a 30-minute walkthrough this week?", "continue"),
        ("Wonderful. Which day and time suits you, and should we come to your office or do a video call?", "continue"),
        ("Thank you, our team will confirm that slot on WhatsApp. Have a good day.", "book_demo"),
    ]
    say, action = script[min(turns - 1, len(script) - 1)] if turns else script[0]
    return {"say": say, "action": action, "language": "en", "callback_time": "", "demo_slot": "", "note": "offline script"}


def make_llm(settings: Settings, store: Store) -> LLM:
    if settings.anthropic_api_key:
        return ClaudeLLM(settings, store)
    log.warning("ANTHROPIC_API_KEY not set: using the offline script (good for rehearsals only)")
    return OfflineLLM()
