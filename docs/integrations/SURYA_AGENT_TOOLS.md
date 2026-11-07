# Surya voice agent: custom tools, Google Sheet and WhatsApp

Status: the Sangam side is built and tested (`/agent-callbacks`, plus best-effort forwarding). Nothing is wired into Sarvam yet, because each step below needs something only you can provide: a public URL, a deployed script, and WhatsApp credentials.

## 1. The design: one tool, Sangam fans out

The agent gets **one** custom tool, `log_callback_request`. It posts to Sangam. Sangam saves the request (the record of truth), then forwards it to the Google Sheet and to staff on WhatsApp in the background.

One tool, not three, because every tool call adds a pause the caller hears, and three calls can half-succeed. Forwarding failures never reach the caller.

```
Caller -> Sarvam agent -> log_callback_request -> Sangam /agent-callbacks
                                                   |-> saved in the database
                                                   |-> Google Sheet row   (optional)
                                                   |-> WhatsApp to staff  (optional)
```

## 2. Sangam backend (needs a public URL)

Set these in `backend/.env`:

| Setting | Value |
|---|---|
| `AGENT_WEBHOOK_SECRET` | A long random value you generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CALLBACK_SHEET_WEBHOOK_URL`, `CALLBACK_SHEET_WEBHOOK_SECRET` | From section 3 (optional) |
| `WHATSAPP_*` | From section 4 (optional) |

Sarvam must be able to reach the endpoint. A laptop on `localhost` cannot be reached, so either deploy the backend or expose it through a tunnel for the pilot. If it sits behind a firewall, allow Sarvam's IPs (`4.213.167.70`, `35.154.84.150`, per Sarvam's docs). Use HTTPS.

Staff read and update requests with a normal login: `GET /agent-callbacks?status=new` and `PATCH /agent-callbacks/{id}` with `{"status": "contacted"}`. The webhook secret only lets the agent write; it cannot read anything.

Safety built in: phone numbers must be Indian mobiles, anything that could be an Aadhaar number is refused or replaced with `[redacted]`, and a retry with the same `call_id` does not create a duplicate.

## 3. Google Sheet

1. Create a Google Sheet. Open **Extensions, Apps Script**, replace the code with the script below.
2. In Apps Script, **Project Settings, Script properties**, add `WEBHOOK_SECRET` with a long random value (a different one from the Sangam secret).
3. **Deploy, New deployment, Web app**. Execute as: you. Who has access: **Anyone**. Copy the web app URL.
4. Put the URL in `CALLBACK_SHEET_WEBHOOK_URL` and the same secret in `CALLBACK_SHEET_WEBHOOK_SECRET`.

The URL is open to anyone, so the secret check is what protects the sheet. The script also neutralises cell values that start with `=`, `+`, `-` or `@`, because a caller's words end up in your sheet and could otherwise become a spreadsheet formula.

```javascript
const HEADERS = ["received_at", "caller_name", "caller_phone", "service",
  "preferred_time", "language", "urgency", "notes", "call_id", "status"];

function safe(v) {
  const s = v == null ? "" : String(v);
  return /^[=+\-@]/.test(s) ? "'" + s : s; // stop formula injection
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  let data;
  try { data = JSON.parse(e.postData.contents); }
  catch (err) { return reply({ ok: false, error: "bad json" }); }

  const secret = PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET");
  if (!secret || data.secret !== secret) return reply({ ok: false, error: "unauthorised" });

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const book = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = book.getSheetByName("Callbacks") || book.insertSheet("Callbacks");
    if (sheet.getLastRow() === 0) sheet.appendRow(HEADERS);

    // A retry with the same call_id must not add a second row.
    if (data.call_id) {
      const ids = sheet.getRange(2, 9, Math.max(sheet.getLastRow() - 1, 1), 1).getValues().flat();
      if (ids.indexOf(data.call_id) !== -1) return reply({ ok: true, duplicate: true });
    }

    sheet.appendRow([
      new Date(), safe(data.caller_name), safe(data.caller_phone), safe(data.service),
      safe(data.preferred_time), safe(data.language), safe(data.urgency),
      safe(data.notes), safe(data.call_id), safe(data.status),
    ]);
    return reply({ ok: true });
  } finally {
    lock.releaseLock();
  }
}
```

## 4. WhatsApp (needs your Meta business setup)

I cannot do this part and have not tested it against the real API. You need:

1. A WhatsApp Business Platform account and a phone number registered with it.
2. A long-lived access token (a system user token). **Keep it secret.** It goes in `WHATSAPP_ACCESS_TOKEN` and nowhere else.
3. The phone number ID (`WHATSAPP_PHONE_NUMBER_ID`) and a currently supported Graph API version (`WHATSAPP_GRAPH_VERSION`). Check Meta's docs for the current version.
4. An **approved message template**, because WhatsApp only allows free-form messages inside a 24-hour window after the recipient writes to you. Category: utility. Name: `surya_new_callback`. Language: English. Body, with exactly five placeholders in this order:

   `New callback request: {{1}} ({{2}}) wants help with {{3}}. Preferred time: {{4}}. Urgency: {{5}}.`

5. The staff numbers, with country code, comma separated, in `WHATSAPP_STAFF_NUMBERS`.

Meta charges per message; I did not verify current pricing.

## 5. The Sarvam tool

Add it under the agent's **Tools, Custom tools, Add tool** once sections 2 and 3 are done. Enter the secret in Sarvam's masked **Secrets** field yourself.

| Field | Value |
|---|---|
| Name | `log_callback_request` |
| Description | Save a visit or callback request for the Surya Enterprises team. Use it once, after the caller has confirmed their name, phone number, service and preferred time. |
| Method and URL | `POST` `https://YOUR-PUBLIC-HOST/agent-callbacks` |
| Auth | API key, header `X-Webhook-Secret`, value from Sarvam Secrets |
| Body fields | `caller_name`, `caller_phone`, `service` (one of aadhaar, pan, banking_financial, utility_bills, travel_tickets, epfo_pf, meeseva_govt, passport_id, not_offered, unclear), `preferred_time`, `language`, `urgency` (normal or urgent), `notes`, `call_id` (the Interaction ID variable) |
| Max wait | 5 seconds |
| If it fails, say | "I could not save that just now, but the team will still try to reach you." |

Then add this to the agent's TOOLS section, **only after the tool works**:

> When the caller has confirmed their name, phone number, service and preferred time, use log_callback_request once, then tell them it is noted. If the tool fails, say the team will still try to reach them and that they can call again if they do not hear back. Never say it is saved unless the tool succeeded. Never put an Aadhaar number, OTP, PIN, password or card number into any field.

## 6. Known limits

- **One business.** Any logged-in Sangam user can list and update callbacks. There is no per-customer separation yet, so do not reuse this for a second customer without adding it (see the scaling architecture doc).
- **No live test.** The Sheet and WhatsApp forwarders are tested with a fake transport only.
- **Phone check is a heuristic.** A 12-digit number that starts with 91 and then a 6-9 is accepted as a phone number, and a real Aadhaar number could occasionally look like that.
- **Nothing retries.** A failed forward is logged and dropped. The record is still in Sangam, so the Sheet and WhatsApp are convenience copies.
