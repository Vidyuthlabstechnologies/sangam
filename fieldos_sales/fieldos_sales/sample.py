"""Made-up campaign data so the dashboard can be seen before any real call.

Every firm is called "Sample firm NN" and the database is flagged sample=1, which puts a
banner on the dashboard. Nothing here is real and nothing is sent.
"""
from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta

from .store import Store, iso

SEGMENTS = ["Developer", "Contractor", "Interiors", "Infra / EPC", "Architect-builder"]
PAINS = ["labour attendance disputes", "advances paid twice", "material short deliveries", "no daily site report",
         "late bills from site", "owner can't see progress", "petty cash not tracked", "drawings out of date on site"]
METHODS = ["paper register", "excel", "whatsapp groups", "another app", "paper register", "whatsapp groups"]
OBJ = ["no_time", "not_decision_maker", "already_using_app", "price_concern", "send_details_first", "bad_timing", "no_need"]
TIPS = ["Ask how many sites before explaining features.", "Keep the first answer under two sentences.",
        "Offer the walkthrough earlier when they mention attendance disputes.",
        "When the receptionist answers, ask for the person who handles site accounts.",
        "Use Telugu sooner when the caller greets in Telugu.", "Mention offline mode when they say sites have poor signal."]


def build(store: Store, seed: int = 7, now: datetime | None = None) -> None:
    rng = random.Random(seed)
    now = now or datetime.now(UTC)
    store.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('sample', '1')")
    for i in range(1, 49):
        store.upsert_prospect({"id": i, "firm": f"Sample firm {i:02d}", "segment": rng.choice(SEGMENTS),
                               "priority": rng.choice(["A - best fit", "A - best fit", "B - good", "C - later"]),
                               "phones": [f"+9190000{i:05d}"]})
        if i <= 44:
            store.save_profile(i, {"summary": "sample", "confidence": "medium"})
        if i <= 40:
            store.save_draft(i, "wa_opener", "Sample opener. Reply STOP and we won't message again.")
            store.save_draft(i, "call_brief", "Sample brief")
            store.approve(i, rng.choice(["call", "whatsapp", "call"]))

    sid = 0
    for pid in range(1, 41):
        phone = f"+9190000{pid:05d}"
        firm_lang = rng.choice(["en", "en", "hi", "te"])
        for _attempt in range(rng.choice([1, 1, 2])):
            day = now - timedelta(days=rng.randint(0, 13))
            ist_hour = rng.choice([10, 11, 11, 12, 13, 14, 15, 16, 16, 17, 18])
            at = day.replace(hour=ist_hour, minute=rng.randint(0, 59), second=0, microsecond=0) - timedelta(hours=5, minutes=30)
            while at.astimezone(UTC).weekday() >= 5:  # calls go out Mon-Fri
                at -= timedelta(days=1)
            sid += 1
            call_sid = f"SAMPLE{sid}"
            answer_p = 0.62 if 11 <= ist_hour <= 12 or 16 <= ist_hour <= 17 else 0.38
            answered = rng.random() < answer_p
            store.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES (?, ?, ?, ?, ?)",
                          (call_sid, pid, phone, "completed" if answered else rng.choice(["no-answer", "busy"]), iso(at)))
            store.log("call", "out", prospect_id=pid, phone=phone, outcome="dialled", meta={"call_sid": call_sid}, at=at)
            if not answered:
                continue
            turns = rng.choice([0, 1, 1, 2, 3, 4, 5, 6, 7, 9])
            r = rng.random()
            if turns <= 1:
                outcome = "ended"
            elif r < 0.07:
                outcome = "opted_out"
            elif turns >= 5 and r < 0.45:
                outcome = "demo_booked"
            elif r < 0.6:
                outcome = rng.choice(["callback_later", "send_info"])
            elif r < 0.75:
                outcome = "not_now"
            else:
                outcome = "ended"
            lines = ["AI: Good morning ji! This is Priya, an AI assistant from FieldOS, ML Dynamic Solutions here in Hyderabad. "
                     "This call is recorded. Do you have two minutes?"]
            for t in range(turns):
                lines.append("Prospect: " + rng.choice(["Haan, boliye.", "We have four sites running.", "We use a register for attendance.",
                                                       "Is this a robot?", "How much does it cost?", "Send me details on WhatsApp.",
                                                       "Our supervisor sends photos in the group."]))
                lines.append("AI: " + rng.choice(["Achha ji. How do your supervisors send attendance today?",
                                                  "That is exactly where FieldOS helps. Could I show you in a 30-minute walkthrough?",
                                                  "Fair question! Our team gives a written proposal after a short site walkthrough. Shall I set that up?"]))
            lat = [rng.randint(1100, 2600) for _ in range(max(1, turns))]
            meta = {"call_sid": call_sid, "duration_s": round(12 + turns * rng.uniform(14, 26), 1), "prospect_turns": turns,
                    "price_asks": int(rng.random() < 0.3), "language": firm_lang, "languages": [firm_lang],
                    "latency_ms_avg": int(sum(lat) / len(lat)), "latency_ms_p90": max(lat),
                    "barge_ins": rng.choice([0, 0, 1, 2]), "silence_prompts": int(rng.random() < 0.15),
                    "ended_by": "caller" if outcome == "ended" else "agent",
                    "voice": "bulbul:v3/priya" if sid % 2 else "bulbul:v4-flash/simran_hi_sales"}
            end_at = at + timedelta(seconds=meta["duration_s"])
            tid = store.log("call", "transcript", prospect_id=pid, phone=phone, text="\n".join(lines), outcome=outcome,
                            meta=meta, at=end_at)
            if outcome != "ended":
                store.log("call", "event", prospect_id=pid, phone=phone, outcome=outcome, at=end_at,
                          meta={"note": rng.choice(["Owner wants to see labour module", "Call after 5 pm", "Send the brochure",
                                                    "Wants to talk to a person", ""]),
                                "demo_slot": rng.choice(["Thu 4 pm", "Sat 11 am", "Mon 3 pm"]) if outcome == "demo_booked" else "",
                                "callback_time": rng.choice(["tomorrow evening", "next week"]) if outcome == "callback_later" else ""})
            if outcome == "opted_out":
                store.suppress(phone, "asked to stop", "sample")
            interest = {"demo_booked": "hot", "callback_later": "warm", "send_info": "warm", "not_now": "cold",
                        "opted_out": "none", "ended": "none" if turns <= 1 else "cold"}[outcome]
            summary = {
                "summary": f"Sample conversation with {turns} prospect turns. Outcome: {outcome.replace('_', ' ')}.",
                "interest": interest, "sentiment": "positive" if interest == "hot" else "negative" if interest == "none" else "neutral",
                "decision_maker": rng.choice(["yes", "no", "unknown"]), "current_method": rng.choice(METHODS),
                "competitors": ["Onsite"] if rng.random() < 0.12 else ["Powerplay"] if rng.random() < 0.08 else [],
                "pains": rng.sample(PAINS, k=rng.choice([0, 1, 2])) if turns > 1 else [],
                "objections": rng.sample(OBJ, k=rng.choice([0, 1, 1, 2])) if outcome != "demo_booked" else [],
                "why_ended": {"demo_booked": "booked_demo", "callback_later": "callback", "send_info": "wants_info",
                              "not_now": "not_interested", "opted_out": "opted_out"}.get(outcome, "hung_up_early" if turns <= 1 else "not_interested"),
                "next_step": "Confirm the walkthrough on WhatsApp" if outcome == "demo_booked" else "",
                "agent_mistakes": ["Long first answer"] if rng.random() < 0.2 else ["Repeated the same question"] if rng.random() < 0.1 else [],
                "coaching_tip": rng.choice(TIPS),
            }
            store.execute("INSERT INTO call_insights (key, prospect_id, channel, touch_id, source_count, data, created_at) "
                          "VALUES (?, ?, 'call', ?, 1, ?, ?)", (f"call:{tid}", pid, tid, json.dumps(summary), iso(end_at)))

    for pid in range(20, 41):
        phone = f"+9190000{pid:05d}"
        at = (now - timedelta(days=rng.randint(1, 12))).replace(hour=rng.randint(5, 12), minute=rng.randint(0, 59), second=0, microsecond=0)
        store.execute("INSERT INTO wa_outbox (prospect_id, phone, text, kind, status, created_at, sent_at) VALUES (?, ?, ?, 'opener', 'sent', ?, ?)",
                      (pid, phone, "Sample opener", iso(at), iso(at)))
        store.log("whatsapp", "out", prospect_id=pid, phone=phone, text="Sample opener. Reply STOP and we won't message again.",
                  outcome="sent", meta={"kind": "opener"}, at=at)
        if rng.random() < 0.4:
            reply_at = at + timedelta(minutes=rng.randint(10, 300))
            store.log("whatsapp", "in", prospect_id=pid, phone=phone, text="Tell me more, we have 3 sites.", at=reply_at)
            store.log("whatsapp", "out", prospect_id=pid, phone=phone, outcome="reply", at=reply_at + timedelta(minutes=1),
                      text="I'm FieldOS's AI assistant. How do your supervisors send attendance today, sir?")
            if rng.random() < 0.5:
                store.log("whatsapp", "in", prospect_id=pid, phone=phone, text="Register. Come on Friday.", at=reply_at + timedelta(minutes=9))
                store.log("whatsapp", "event", prospect_id=pid, phone=phone, outcome="demo_booked", at=reply_at + timedelta(minutes=10),
                          meta={"note": "Booked on WhatsApp", "demo_slot": "Fri 11 am", "callback_time": ""})
                store.execute("INSERT OR REPLACE INTO wa_chats (phone, prospect_id, mode, ai_disclosed, updated_at) VALUES (?, ?, 'human', 1, ?)",
                              (phone, pid, iso(reply_at)))

    for d in range(14):
        day = (now - timedelta(days=d)).date().isoformat()
        for purpose, usd in (("call_turn", rng.uniform(0.02, 0.09)), ("insight_summary", rng.uniform(0.003, 0.01)),
                             ("research", rng.uniform(0.0, 0.03)), ("whatsapp_turn", rng.uniform(0.0, 0.01))):
            store.execute("INSERT INTO llm_usage (day, purpose, input_tokens, output_tokens, usd) VALUES (?, ?, 0, 0, ?)", (day, purpose, usd))

    store.execute("INSERT INTO insight_reports (data, created_at) VALUES (?, ?)", (json.dumps({
        "headline": "Sample review: calls answered between 11 am and 12 pm and after 4 pm book twice as many walkthroughs.",
        "what_works": ["Asking how attendance is tracked today keeps people talking", "WhatsApp replies that mention offline mode"],
        "what_hurts": ["Long first answers: most hang-ups happen after the first reply", "Reply delay above 2 seconds in Telugu calls"],
        "changes": [
            {"change": "Shorten the first reply after the greeting to one question.", "why": "Sample: 38% of hang-ups come after turn 1.", "area": "opening"},
            {"change": "Move calls to 11 am to 12 pm and 4 pm to 6 pm.", "why": "Sample: those hours are answered about 60% of the time vs 38%.", "area": "timing"},
            {"change": "Ask for the site accounts person when a receptionist answers.", "why": "Sample: 'not decision maker' is a top objection.", "area": "script"},
        ]}), iso(now)))
