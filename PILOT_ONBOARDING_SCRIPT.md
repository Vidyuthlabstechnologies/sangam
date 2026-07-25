# Sangam Pilot Customer Onboarding Script
## Version 1.0 | For Internal Use Only

---

## 📋 PRE-ONBOARDING CHECKLIST (Complete Before Day 1)

### Customer Qualification (Done During Sales)
- [ ] Company registered in India (CIN/LLPIN)
- [ ] Active GSTIN (verify on GSTN portal)
- [ ] Monthly vendor payments > ₹5L
- [ ] Active Razorpay account (or willing to create)
- [ ] Technical contact identified (name, email, phone)
- [ ] Decision maker identified (CEO/COO/CFO)

### Technical Prerequisites (Customer Must Provide)
- [ ] GSTIN (for GSTN validation)
- [ ] CIN/LLPIN (for MCA validation)
- [ ] Udyam number (if MSME)
- [ ] PAN (for PAN validation)
- [ ] UAN (for EPFO, if >20 employees)
- [ ] ICEGATE credentials (if importer)
- [ ] IEC code (if exporter)
- [ ] RERA registration (if real estate)
- [ ] FSSAI license (if food)
- [ ] GeM registration (if govt vendor)
- [ ] Razorpay test/live keys

---

## 🗓️ DAY 1: KICKOFF & SETUP (2-3 Hours)

### 1.1 Welcome & Platform Overview (30 min)
**Script:**
> "Welcome to Sangam. We're going to connect your existing business data — GST, MCA, banking, compliance — into one workflow. No more jumping between portals. Let me show you the flow..."

**Demo Flow (10 min):**
1. Login → Dashboard (real-time status)
2. Create workflow → "Vendor Onboarding" template
3. Add vendor → Auto-fetch GST/MCA/Udyam
4. Approval chain → Assign roles
5. Payment → Razorpay escrow
6. Compliance → Auto-track GST returns, MCA filings

### 1.2 Technical Setup (60-90 min)

#### A. Razorpay Integration (15 min)
```bash
# Customer does this in Razorpay Dashboard
1. Settings → API Keys → Generate Test Keys
2. Webhooks → Add URL: https://api.sangam.ai/payments/webhook
   Events: payment.captured, payment.failed, refund.processed
3. Share: Key ID, Key Secret (test mode)
```

**Verify:**
```bash
# Test webhook
curl -X POST https://api.sangam.ai/payments/webhook \
  -H "Content-Type: application/json" \
  -d '{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test","amount":10000}}}}'
```

#### B. Government API Credentials (30 min)

| Credential | Where to Get | Format |
|------------|--------------|--------|
| **GSTN GSP** | GSTN GSP Portal | Client ID + Secret |
| **MCA API** | MCA21 Portal | API Key |
| **Udyam** | KredX/Udyam API | API Key |
| **NSDL PAN** | NSDL e-Gov | API Key |
| **EPFO** | EPFO Employer Portal | API Key |
| **DigiLocker** | DigiLocker Developer | Client ID + Secret |
| **DGFT IEC** | DGFT Portal | API Key |
| **ICEGATE** | ICEGATE Portal | User ID + Password |
| **RERA** | State RERA Portal | API Key (per state) |
| **FSSAI** | FoSCoS Portal | License No + API Key |
| **GeM** | GeM Portal | Vendor ID + API Key |
| **ICEGATE** | ICEGATE Portal | User ID + Password |
| **MoSPI/NSO** | data.gov.in | API Key |

**Action:** Customer enters in Sangam Settings → Integrations

#### C. Sarvam AI (5 min)
```bash
# Already configured with platform key
# Customer only needs to test:
curl -X POST https://api.sangam.ai/ai/translate \
  -H "Authorization: Bearer <token>" \
  -d '{"text":"Hello","target_language_code":"hi-IN"}'
```

#### D. WebSocket Test (5 min)
```bash
# In browser console:
const ws = new WebSocket("wss://api.sangam.ai/ws?token=<token>");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({type: "ping"}));
```

### 1.3 First Workflow Creation (30 min)

**Template: "Standard Vendor Onboarding"**

```json
{
  "name": "Vendor Onboarding - [Customer Name]",
  "description": "Complete vendor onboarding with compliance checks",
  "phases": [
    "initiation",
    "compliance_check",
    "approval",
    "execution",
    "verification",
    "settlement"
  ],
  "actors": [
    {"role": "initiator", "email": "procurement@customer.com"},
    {"role": "approver", "email": "finance@customer.com"},
    {"role": "compliance", "email": "compliance@customer.com"},
    {"role": "vendor", "email": "vendor@vendor.com"}
  ]
}
```

**Walkthrough:**
1. Create workflow → Select template
2. Add test vendor → Enter GSTIN → Auto-fetch details
4. Assign compliance officer → Auto-check GST returns, MCA status
5. Submit for approval → Finance approves
6. Execute → Generate PO → Vendor receives notification
6. Vendor delivers → Upload invoice → Auto-match GST returns
7. Verify → Release escrow payment

---

## 📅 DAY 2-7: LIVE PILOT (1 Week)

### Daily Check-ins (15 min standup)
- **Morning (9:30 AM):** "What ran yesterday? What's blocked?"
- **Evening (5:30 PM):** "What completed? Any errors?"

### Pilot Scenarios (Must Complete All)

| Scenario | Steps | Success Criteria |
|----------|-------|------------------|
| **1. New Vendor Onboarding** | Add vendor → GST/MCA check → Approve → PO → Payment | < 30 min end-to-end |
| **2. Existing Vendor Re-verification** | Re-run GST/MCA check → Flag changes | Auto-flag changes |
| **3. Payment with Escrow** | Create PO → Escrow → Delivery → Release | Funds held → Released on verify |
| **4. Compliance Alert** | GST return overdue → Auto-flag → Escalate | Alert in < 5 min |
| **5. Multi-currency Payment** | INR + USD vendor → Razorpay Intl | Settlement in 24h |
| **6. Mobile Approval** | Finance approves on Android app | < 30 sec on mobile |
| **7. Voice Workflow** | Field team creates PO via voice | Hindi/English recognized |

### Error Scenarios (Must Test)
| Scenario | Expected Behavior |
|----------|-------------------|
| GSTN API down | Graceful fallback, retry with backoff |
| Razorpay webhook timeout | Idempotency key prevents double charge |
| GSTIN invalid | Clear error: "Invalid GSTIN format" |
| MCA API timeout | Retry 3x, then queue |
| Network loss (mobile) | Offline queue, sync on reconnect |

---

## 📊 WEEK 2-4: SCALE & MEASURE

### Success Metrics (Track Weekly)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Workflow Completion Rate** | > 90% | Completed / Started |
| **Avg Workflow Time** | < 2 hours | Created → Settled |
| **Compliance Check Accuracy** | > 99% | Auto-flag vs manual |
| **Payment Success Rate** | > 99.5% | Captured / Initiated |
| **Mobile App Usage** | > 50% of approvals | App analytics |
| **Compliance Auto-flag** | < 5 min | Alert timestamp |
| **Support Tickets** | < 2/week | Zendesk/Slack |

### Weekly Review (Friday 4 PM)
**Agenda (30 min):**
1. Metrics review (10 min)
2. Bugs/blockers (10 min)
3. Feature requests (5 min)
4. Next week plan (5 min)

### Customer Feedback Collection
**Week 2:** NPS Survey (1-10) + "What's one thing to fix?"
**Week 4:** Deep interview (30 min) → Case study permission

---

## 📝 ONBOARDING DELIVERABLES (Handoff Package)

### Customer Receives:
- [ ] **API Credentials Sheet** (all keys in password manager)
- [ ] **Workflow Templates** (JSON export + documentation)
- [ ] **API Documentation** (Postman collection + OpenAPI)
- [ ] **Mobile App** (APK/AAB + login credentials)
- [ ] **Runbook** (common issues + solutions)
- [ ] **Escalation Matrix** (Slack channel + phone + email)
- [ ] **Compliance Calendar** (GST due dates, MCA filings, etc.)

### Internal Handoff (Customer Success):
- [ ] Customer profile in CRM
- [ ] Billing setup (monthly/annual)
- [ ] Feature flags enabled
- [ ] Monitoring alerts configured
- [ ] Backup admin access

---

## 🚨 ESCALATION MATRIX

| Severity | Response Time | Channel | Contact |
|----------|---------------|---------|---------|
| **P0 - Platform Down** | 15 min | Phone + Slack | Platform Lead |
| **P1 - Payment Failed** | 30 min | Slack + SMS | Payments Lead |
| **P2 - Compliance Alert Missed** | 1 hour | Slack | Compliance Lead |
| **P3 - Feature Bug** | 4 hours | Slack | Engineering |
| **P4 - Question/Enhancement** | 24 hours | Email | Support |

---

## ✅ GO/NO-GO CRITERIA (End of Week 4)

### GO (Convert to Paid)
- [ ] ≥ 80% workflow completion rate
- [ ] ≥ 5 workflows/week
- [ ] Zero P0/P1 incidents unresolved > 24h
- [ ] NPS ≥ 7
- [ ] Customer signs MSA

### NO-GO (Extend Pilot)
- [ ] Workflow completion < 60%
- [ ] > 2 P0 incidents
- [ ] NPS < 5
- [ ] Critical integration broken > 24h

---

## 📞 CONTACTS

| Role | Name | Slack | Email | Phone |
|------|------|-------|-------|-------|
| **Platform Lead** | | | | |
| **Payments Lead** | | | | |
| **Compliance Lead** | | | | |
| **Engineering Lead** | | | | |
| **Customer Success** | | | | |

---

## 📁

---

## 📎 APPENDIX: QUICK REFERENCE

### API Base URLs
```
Production:  https://api.sangam.ai
Staging:     https://staging-api.sangam.ai
WebSocket:   wss://api.sangam.ai/ws
```

### Key Endpoints
```
POST   /auth/login
POST   /workflows
GET    /workflows/{id}
POST   /workflows/{id}/transition
POST   /payments/initiate
POST   /payments/escrow
POST   /govstack/gstn/validate
POST   /govstack/mca/company
POST   /govstack/udyam/validate
POST   /govstack/pan/validate
POST   /govstack/epfo/validate
POST   /govstack/icegate/track
POST   /govstack/rera/validate
POST   /govstack/fssai/validate
POST   /govstack/gem/validate
POST   /ai/translate
POST   /ai/llm
POST   /ai/speech-to-text
GET    /ws?token=<jwt>
```

### WebSocket Events
```json
// Subscribe to workflow
{"type": "subscribe_workflow", "workflow_id": "uuid"}
// Voice chunk
{"type": "voice_chunk", "audio": "base64", "language": "hi-IN"}
// Ping
{"type": "ping"}
```

### Rate Limits
| Endpoint | Limit |
|----------|-------|
| General API | 60/min |
| AI Endpoints | 10/min |
| GovStack | 30-60/min |
| Payments | 20/min |

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Next Review:** Post-Pilot Review Meeting