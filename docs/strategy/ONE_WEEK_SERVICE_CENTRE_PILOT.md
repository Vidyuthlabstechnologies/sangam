# One-week pilot plan: Hyderabad service centres

Date: 2026-11-07. Goal: 3-5 signed pilots in one week, with numbers you can show Rishi to justify going to other industries.

## 0. Read this first

- **The product does not serve service centres yet.** Sangam today is built around pharma. A service-centre pilot needs a small new "pack" (section 2). I have not scoped how long that takes. Do not promise a feature to a customer that is not built.
- **Everything marked (assumption) is a starting number to tune, not a fact.** Prices, close rates and ad budgets are guesses until the first five conversations.
- **Be honest about what a week can prove.** Three signed pilots proves your network trusts you. It does not prove the product earns money from small centres. Section 8 says how to word that to Rishi.

## 1. Who we are selling to, and why they would care

A centre like Surya Enterprises sells many unrelated services (Aadhaar, PAN, bill payments, tickets, PF, MeeSeva certificates, passport and ID help). Each service has its own documents, portal and failure modes. The likely pains, to **confirm in the first visits, not assume**:

1. Applications rejected or repeated because a document was missing.
2. Customers returning to ask "what happened to my application?"
3. No clear record of what was done, for whom, and what fee was earned, which matters in a dispute.
4. Owner cannot see what staff did during the day.

Scope of services for the pilot (from your list, with 6, 7, 8, 12, 13 removed): Aadhaar, PAN, banking and financial, utility bills, travel tickets, EPFO/PF, MeeSeva and government services, passport and ID.

## 2. Pilot v0: the smallest thing worth paying for

Build only this for week one:

| Part | What it does | Notes |
|---|---|---|
| Service catalogue | The 8 sections as job types, each with a **document checklist** and status stages: received, submitted, approved/rejected, delivered | Configuration of the existing workflow engine, not new engine code |
| Job record | Staff log a job in under a minute; checklist stops "submitted" until complete | Staff-facing web or Android |
| Status for the customer | One message to the customer when the status changes | WhatsApp/SMS cost and approval not checked |
| Owner's daily summary | Jobs by service, completed, pending, fees recorded | The thing owners will look at |
| Telugu/Hindi voice note intake | Staff speak the job; transcript fills the form | **Stretch.** Sarvam lists speech-to-text for 22 languages; I did not confirm Telugu specifically |

**Deliberately out of v0:** cash and AEPS handling, payments, any automation of government portals, storing ID document images or full Aadhaar numbers (section 7).

## 3. The scoreboard (one sheet, updated daily at 7 pm)

Every number has an owner and a source. If it is not in the sheet, it did not happen.

| Metric | Definition | Week-1 target (assumption) | Source |
|---|---|---|---|
| **Closed pilots** (the headline) | Signed pilot agreement **and** first fee received | **3, stretch 5** | Bank/UPI record + signed form |
| Warm contacts reached | Centres actually spoken to | 25 | BD visit log |
| Meetings held | Face-to-face or video with an owner | 13 | BD visit log |
| Demos done | Product shown on a phone | 8 | BD visit log |
| Demo-to-close rate | Closed / demos | 40% | Computed |
| Centres live | Staff trained **and** 10+ real jobs logged | 2+ | Product data |
| Jobs logged | Total real jobs in week 1 | 60+ | Product data |
| Time per job | Stopwatch, 10 jobs before vs 10 after | Report the real number | Baseline sheet |
| Rejected/missing-document jobs | Before vs after, per centre | Report the real number | Centre's own tally |
| Would pay again | Owner says yes at day 7 and day 14 | 2 of 3 | Call log |
| Marketing leads / cost per lead | See section 5 | Report, cap spend | Ad dashboard |

Funnel arithmetic behind the targets (assumptions): 3 closes at 40% needs about 8 demos; at about 60% show-up that needs about 13 booked meetings; at about 50% reachability that needs about 25 warm contacts.

## 4. Day by day

| Day | Do | Done when |
|---|---|---|
| 1 | Fix the offer and pilot price. Build the scoreboard sheet. List 25 warm centres with phone numbers. Visit Surya Enterprises: record how a job really flows, time 10 jobs, note the top 3 pains. | Sheet live; 25 contacts listed; baseline captured |
| 2 | Configure pilot v0. Sign and brief the BD manager (script, objection answers, rules in section 6). Launch the landing page and the first small ad set. | v0 demo works on one phone; BD briefed; ads live |
| 3 | 8-10 visits or calls. Demo on the owner's own phone. Send the proposal the same day. | 8+ meetings; proposals out |
| 4 | Demos and closes. Collect the first fee by UPI. Start the first onboarding. | 1-2 closed |
| 5 | Onboard signed centres (30-minute staff session each). First real jobs logged. | First centre live |
| 6 | Second round of closes. Fix the top 3 problems seen in real use. | 3 closed |
| 7 | Count everything. Call every pilot owner. Write the Rishi pack (section 8). | Scoreboard final; pack written |

Hiring a BD manager inside the same week is itself a risk. Plan to do the first Day 1-3 visits yourself so the week does not depend on a hire.

## 5. Digital marketing, in support, not the main engine

One week of paid ads will produce few qualified leads. Treat it as a way to be findable while the BD manager and your own network do the closing.

- Telugu and English landing page with a WhatsApp click-to-chat button and a 60-second demo video.
- WhatsApp messages to centre-owner groups. The Telangana MeeSeva Federation lists thousands of franchise operators ([TGMF](https://www.tgmf.in/pages/about/tgmfNew/aboutUs.php)); go through its leaders rather than spamming.
- Geo-targeted lead ads for Hyderabad small-business owners, Telugu creative.
- Fixed daily spend cap (assumption: set it so the whole week costs less than one closed pilot's first-year revenue).
- Track: leads, cost per lead, lead to meeting, meeting to close. Report them even if they are poor.

## 6. The BD manager: terms to decide, and guardrails

This is an outline, **not legal advice**; have it reviewed before signing.

**Commission, one time per closed centre.** Define "closed" tightly. Suggested: signed agreement **and** first fee received **and** centre live (10 jobs logged). Pay on that, not on signature, so you never pay for a sign-up that never starts. Consider a clawback if the centre refunds or leaves within 30 days.

**Sizing it.** The commission must be well below first-year margin per centre. Illustration only: if a pilot were priced at ₹1,500/month (₹18,000/year) a 20% commission would be ₹3,600. You set the real price and percentage.

**Per diem for travel and food.** Cap per day, paid against a visit log (centre name, time, a photo of the signboard or the owner's signed visit slip). That keeps expenses honest without micromanaging.

**Guardrails.** An approved pitch script and demo only. No promising unbuilt features. No collecting customers' ID documents. No asking centres for portal logins. Credit for centres he sources for a fixed period, so territory disputes do not arise as you expand across Hyderabad.

**Risk of commission-only.** It attracts people who will overpromise. The "closed means live" rule and the script are your protection.

## 7. Compliance guardrails (these can sink the pilot)

- **Aadhaar.** A May 2022 UIDAI advisory said unlicensed private entities cannot keep Aadhaar copies, and told people to use a masked number. The photocopy part was later withdrawn, so its current status is unclear. RBI-regulated entities must mask the first eight digits before storing. For v0: **never store full Aadhaar numbers or Aadhaar images**; store a job reference and at most the last four digits. Get a lawyer's view before storing any ID document. ([LiveLaw](https://www.livelaw.in/amp/news-updates/dont-share-photocopies-of-aadhaar-unlicensed-entities-like-hotels-cant-keep-aadhaar-cards-uidai-200366), [TaxGuru](https://taxguru.in/corporate-law/advisory-sharing-photocopy-aadhaar-withdrawal.html), [Cashfree](https://www.cashfree.com/blog/why-is-aadhaar-masking-mandatory-for-businesses/))
- **AEPS.** RBI's tighter rules for AEPS touchpoint operators apply from 1 January 2026 (stricter KYC, monitoring, one operator with one acquiring bank). Keep AEPS and cash handling out of the pilot; if centres ask for it, say no for now. Check the circulars, since my sources are news and vendor posts. ([Adda247](https://currentaffairs.adda247.com/rbi-tightens-aeps-rules-to-combat-fraud-from-january-2026), [Moneylife](https://moneylife.in/article/aeps-frauds-rbi-suggests-due-diligence-and-restrictions-on-touchpoint-operators/74798.html))
- **MeeSeva franchise terms.** I do not know whether a franchise agreement restricts third-party software. Check with Surya Enterprises or the federation before pitching. Position it as a separate back-office record, with no portal automation and no credential sharing.
- **DPDP.** Customer details are personal data. Put a consent notice at the counter. Most duties apply from about May 2027, but design for it now.
- **Voice.** Speech-to-text covers more languages than text-to-speech, so a spoken read-back may not exist in every language. Verify Telugu.

## 8. What to take to Rishi

One page with: the final scoreboard; two owner quotes; what you learned; and a pre-committed rule so the result cannot be spun. Suggested rule (adjust before the week starts): **expand to another industry only if at least 3 pilots closed, at least 2 went live, and at least 2 of 3 owners say they would pay again.**

Say plainly what is not proven: willingness to pay beyond the pilot, revenue per centre, and whether one week of results hold up over a month. The scale is large (about 5,000 MeeSeva centres statewide per a Nov 2025 report ([AIR](https://www.newsonair.gov.in/telangana-govt-launches-meeseva-on-whatsapp-for-people-to-access-govt-to-citizen-services)), figures vary by source), but each centre is small, so revenue per centre is the number to watch.

## 9. Open questions for you

1. Is Surya Enterprises a customer, a design partner, or just an example?
2. The pilot price, and whether the pilot is free for the first 2 weeks. A free pilot is fine, but then "closed" must mean signed and live, not paid, and the scoreboard should say so.
3. Who builds pilot v0 this week, and what is the honest estimate?
4. Does the BD manager exist yet, or are you doing the first visits?
