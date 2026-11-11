"""Per-prospect call brief and WhatsApp opener, written from the research profile.

Both are drafts for the owner to read before anything is sent. Each is
checked by guardrails.check_outbound(); a draft that mentions pricing is
rewritten once, then replaced by a safe template.
"""
from __future__ import annotations

from typing import Any

from .guardrails import check_outbound
from .knowledge import KNOWLEDGE_TEXT
from .llm import LLM

PITCH_SCHEMA = {
    "type": "object",
    "properties": {
        "call_brief": {"type": "string", "description": "Markdown brief for the calling agent and the human team"},
        "whatsapp_opener": {"type": "string", "description": "First WhatsApp message, under 420 characters"},
    },
    "required": ["call_brief", "whatsapp_opener"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write sales outreach for FieldOS (ML Dynamic Solutions, Hyderabad) to Indian construction firms.\n"
    "Write two things from the prospect profile:\n"
    "1. call_brief (markdown, under 250 words): what the firm does (one line), the 3 FieldOS angles that fit them best "
    "with the reason each matters to THIS firm, 3 discovery questions, the 3 most likely objections with honest answers, "
    "and the goal (book a 30-minute walkthrough with the decision maker). If you include the money question, write it as 'What will it take?' and answer that our team shares a written proposal after a short site walkthrough.\n"
    "2. whatsapp_opener (under 420 characters): warm, respectful Indian business English, one specific detail about "
    "their company from the profile, one question about how they handle the pain today, offer a short walkthrough. "
    "Sign as 'FieldOS team, ML Dynamic Solutions'. End with: 'Reply STOP and we won't message again.' No links, "
    "no emojis except one 🙏 at most.\n"
    "Hard rules: never mention or hint at price, cost, fees, discounts, plans, trials or anything free; never "
    "compare prices with competitors; never invent customers, results or numbers; only use features in the product notes; "
    "if the profile is thin, keep the message general rather than guessing.\n\n"
    "FieldOS product notes:\n" + KNOWLEDGE_TEXT
)


def fallback_opener(prospect: dict[str, Any]) -> str:
    firm = prospect.get("firm") or "your company"
    return (
        f"Namaste, this is the FieldOS team from ML Dynamic Solutions, Hyderabad. We came across {firm}'s projects "
        "and wanted to ask: how does your team keep track of site attendance, spending and deliveries today? "
        "We have built an Android and iPhone app for exactly this, and would be glad to show you in a 30-minute walkthrough. "
        "FieldOS team, ML Dynamic Solutions. Reply STOP and we won't message again."
    )


def write_pitch(prospect: dict[str, Any], profile: dict[str, Any], llm: LLM) -> dict[str, str]:
    user = f"Prospect: {prospect.get('firm')} ({prospect.get('segment')}, {prospect.get('size')})\nProfile: {profile}"
    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
    system = [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]
    for attempt in range(2):
        out = llm.json(purpose="pitch", system=system, messages=messages, schema=PITCH_SCHEMA, max_tokens=1500)
        problems = check_outbound(out["call_brief"]) + check_outbound(out["whatsapp_opener"])
        if len(out["whatsapp_opener"]) > 600:
            problems.append("opener too long")
        if not problems:
            if "STOP" not in out["whatsapp_opener"]:
                out["whatsapp_opener"] = out["whatsapp_opener"].rstrip() + " Reply STOP and we won't message again."
            return out
        messages = [{"role": "user", "content": user + "\n\nYour previous draft broke these rules: "
                     + "; ".join(problems) + ". Rewrite without them. Do not use the words price, cost, free, fee, plan, trial or any amount."}]
    return {
        "call_brief": "Automatic brief failed the pricing check twice. Use the general script: ask how they track "
                      "attendance, spending and deliveries across sites, then offer a 30-minute walkthrough.",
        "whatsapp_opener": fallback_opener(prospect),
    }
