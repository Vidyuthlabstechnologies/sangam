# FieldOS sales agents

AI agents that pitch FieldOS to construction firms, one firm at a time:

1. **Research** each firm from its own website: what it builds, where, how big, and which FieldOS features fit.
2. **Pitch writer**: a call brief and a WhatsApp opener written for that firm.
3. **AI calling agent**: phones the firm (Exotel), listens and speaks in English, Hindi or Telugu (Sarvam), and aims to book a 30-minute walkthrough.
4. **WhatsApp bot**: sends approved openers slowly from your number (WAHA) or the official API (Twilio), answers replies, and hands warm chats to a person.

It lives in the sangam repo because it reuses sangam's Sarvam integration patterns, but it runs on its own: one Python process plus WAHA in Docker, with a local SQLite file. It does not need the sangam backend, Postgres or Temporal.

## Rules built into the code (not just the prompts)

| Rule | Where |
|---|---|
| **Never reveal pricing in any form.** Every line the AI is about to say or send is checked for amounts, ₹/Rs/lakh/crore, "per user/site/month", "free", "trial", "discount", "cheaper than", in English, Hindi and Telugu. A failing line is rewritten once, then replaced with a safe line. Price questions get a fixed answer: our team shares a written proposal after a short site walkthrough. Asked twice, the agent hands over to a person. | `guardrails.py`, `conversation.py` |
| **Says it is an AI** at the start of every call, and in the first WhatsApp reply. Never claims to be human; "are you a robot?" always gets "yes". | `conversation.py` |
| **Opt-out is instant and permanent**: "stop", "don't call", "not interested", "band karo", "vaddu" and similar end the call or chat, add the number to the do-not-contact list and cancel anything queued. | `guardrails.py`, `store.py` |
| **Nothing goes out without you**: live mode is off by default, and each firm must be approved by you, per channel, after you read its drafts. Editing a draft removes the approval. | `compliance.py` |
| **DND / NCPR**: calls need a fresh scrub result ("not registered", under 7 days old) for the number. A number on DND is never called or messaged. | `compliance.py` |
| **Contact hours**: Mon to Sat, 10:00 to 19:00 IST (configurable). | `compliance.py` |
| **Low volume**: max 20 calls and 15 new WhatsApp chats a day, 4 to 9 minutes between WhatsApp sends, no call to the same firm within 7 days or more than twice, WhatsApp stops after 2 unanswered messages. | `compliance.py`, `whatsapp.py` |
| **Only prospects**: the bot ignores every chat on the number that isn't an imported prospect (friends, family, groups). | `whatsapp.py` |
| **Honest claims only**: the AI may only mention features listed in `knowledge.py`, must not invent customers or results, and website text is treated as data, not instructions. | `knowledge.py`, `research.py` |
| **Cheap AI with a hard cap**: Claude Haiku, about $0.0015 to research a firm and well under a cent per call; stops at `LLM_DAILY_BUDGET_USD` (default $1/day) and hands over to a person. | `llm.py` |

## Risks you should know before going live

- **Unofficial WhatsApp (WAHA) can get the number banned.** WhatsApp bans numbers that message many strangers. Use a separate SIM, not your main business number, warm it up with normal chats for a week or two, keep the daily cap low (start with 5 to 10), and only message firms you approved. Twilio (official) avoids bans but cold first messages need a Meta-approved template.
- **AI cold calls in India must follow TRAI's commercial communication rules.** Promotional calls are meant to come from a registered telemarketer on DLT using the 140-series, after scrubbing against the NCPR (DND) register. TRAI has been disconnecting and blacklisting unregistered 10-digit numbers used for promotional calls. Ask Exotel (or your provider) to set up a compliant number and DND scrubbing before the first real call. This guide is not legal advice.
- **Personal data (DPDP Act 2023):** the phone numbers came from firms' public websites. Keep the opt-out list, delete a person's data when asked, and don't buy or scrape personal mobile lists.
- **Not yet tested against the live services from here**: no API keys were available while building, so the Claude answers, the Exotel call stream and the WAHA endpoints are covered by offline tests only. Do the first-run checks below on your own numbers before any prospect.

## Setup

```bash
cd fieldos_sales
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # fill in keys; keep FIELDOS_SALES_LIVE=0
python -m fieldos_sales import "path/to/hyderabad-target-firms.xlsx"
```

Data stays in `fieldos_sales/data/sales.db` (gitignored). Never commit it.

## Daily workflow

```bash
python -m fieldos_sales research --priority A --limit 20   # reads each firm's website
python -m fieldos_sales pitch --priority A --limit 20      # call brief + WhatsApp opener per firm
python -m fieldos_sales review --priority A                # writes data/review.md: read every draft
python -m fieldos_sales show 12                            # one firm in full, and why it can or can't be contacted
python -m fieldos_sales simulate 12                        # rehearse the call: you play the prospect
python -m fieldos_sales simulate 12 --channel whatsapp     # rehearse the chat
python -m fieldos_sales approve --channel whatsapp --ids 1,2,5
python -m fieldos_sales status
```

Nothing above contacts anyone.

## Going live with WhatsApp (WAHA)

1. In `.env`: `WHATSAPP_GATEWAY=waha`, a long random `WAHA_API_KEY` and `WA_WEBHOOK_TOKEN`, your own number in `OWNER_NOTIFY_NUMBER`.
2. `docker compose -f docker-compose.waha.yml --env-file .env up -d`, open http://localhost:3000/dashboard, start the `default` session and scan the QR with the **separate sales phone** (WhatsApp, Linked devices).
3. `python -m fieldos_sales serve` (keep it running; the sender only sends inside contact hours).
4. First test on yourself: import a test row with your own second number, research, pitch, approve, then set `FIELDOS_SALES_LIVE=1`, restart `serve`, and run `python -m fieldos_sales wa-queue --ids <test id>`. Reply to it, then reply STOP, and check `show <id>`.
5. For real prospects: `wa-queue --ids ...` for the approved firms; `wa-followups` once a day queues one gentle follow-up where an opener got no reply after 3 days.

When a prospect agrees to a walkthrough or asks for a person, the bot stops replying in that chat and sends you an alert on WhatsApp. Take over from the sales phone.

Twilio instead: `WHATSAPP_GATEWAY=twilio`, the `TWILIO_*` values, `PUBLIC_BASE_URL`, and point the Twilio sender's webhook at `https://YOUR-HOST/wa/twilio`.

## Going live with calls (Exotel + Sarvam)

1. Exotel account with a compliant promotional (140-series) caller ID and DND scrubbing. Put the SID, API key/token and caller ID in `.env`.
2. Make the server reachable over HTTPS (for a trial, a tunnel such as `cloudflared tunnel --url http://localhost:8090`) and set `PUBLIC_BASE_URL` and a long random `VOICE_STREAM_TOKEN`.
3. In Exotel App Bazaar, make a flow: **Voicebot** applet with URL `wss://YOUR-HOST/exotel/stream?token=VOICE_STREAM_TOKEN`, then **Hangup**. Put that flow's URL in `EXOTEL_FLOW_URL`.
4. `SARVAM_API_KEY` for speech (the shared FieldOS Sarvam key works).
5. Get the scrub result for the numbers you want to call as a CSV with `phone,dnd` columns and load it: `python -m fieldos_sales import-dnd scrub.csv`.
6. `approve --channel call --ids ...`, `FIELDOS_SALES_LIVE=1`, `serve` running, then `python -m fieldos_sales call <id>`. **Call your own phone first** (a test prospect row) and check the greeting, the turn-taking delay (about 2 to 3 seconds), the Hindi/Telugu switch and "stop calling me".

Only calls placed by `call` get the agent; any other stream is refused.

## Making calls feel natural

See [CALL_PLAYBOOK.md](CALL_PLAYBOOK.md): what makes people hang up, what the agent does about it, and what to tune in the first week.

## Keeping it accurate

`knowledge.py` is the only source of product claims. Update it when the app changes (for example when the app goes public on Play, or a web dashboard ships). `tests/test_guardrails.py` fails if a price slips into it or into any fixed line.

## Tests

```bash
pip install -r requirements.txt
python -m pytest -q tests
```

All tests run offline: no API keys, no network, nothing sent.
