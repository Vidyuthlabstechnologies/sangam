"""What the agents may say about FieldOS.

Every claim the AI makes must come from this file. Keep it honest: if a
feature is not shipped, say so here and the agent will describe it as being
built. There are deliberately NO prices anywhere in this file.

Update this when the app changes. Sources: project files sales/enterprise/
(buyer one-pager, demo scripts), marketing/03-outreach-kit.md, and the
FieldOS repo as of 11 Nov 2026 (app 1.7.5).
"""
from __future__ import annotations

COMPANY = {
    "name": "ML Dynamic Solutions Private Limited",
    "city": "Hyderabad (Hi-Tech City, Madhapur)",
    "email": "info@mldynamic.com",
    "website": "fieldos-mldynamic.netlify.app",
}

PRODUCT_ONE_LINER = (
    "FieldOS is an Android and iPhone app that lets site supervisors record attendance, "
    "spending, deliveries and daily progress from the site, even with no signal, so owners "
    "and project managers can check and approve every site's week without phone calls."
)

# (feature, what it does for the customer)
FEATURES: list[tuple[str, str]] = [
    ("Works offline", "Everything saves on the phone at sites with no network and syncs when signal returns."),
    ("GPS and selfie attendance", "Supervisors punch in a whole labour gang in one tap; GPS and selfie checks stop padded hajri."),
    ("Weekly wage sheet with advances", "Wages are worked out from attendance, and advances are recorded against each worker, so Saturday payouts stop being disputed."),
    ("Money book", "Every site expense with a bill photo, GST and voucher number, so accounts is not guessing at month end."),
    ("Purchase orders and goods receipts", "The supervisor records each delivery against the PO with a photo of the slip; the PO shows what came and what is still due."),
    ("Material stock and stores", "Stock received and issued at each site, central warehouse and transfers between sites, and a tools register."),
    ("Weekly site close and approvals", "One review queue for each site; the PM approves or sends items back with a reason, with approval rules by amount up to the owner."),
    ("Daily Site Brief", "One screen for the owner showing which sites need attention today, including sites where the report is missing."),
    ("Daily progress report by voice", "Supervisors speak the DPR in Hindi, Telugu, Tamil, Kannada, Marathi or English, and a PDF goes to the WhatsApp group."),
    ("Stamped site photos", "Date, time and location on every photo, so billing disputes end quickly."),
    ("Measurement book and RA billing", "Measurements flow into running-account bills, with retention and variations tracked."),
    ("Tally and Zoho export", "Checked site vouchers export as Tally XML or Zoho CSV, so FieldOS feeds the accounts system instead of replacing it."),
    ("Subcontractor, supplier and client portals", "Outside parties get their own limited login and see only their own work orders, quotes or progress."),
    ("Supplier quote comparison", "Compare supplier quotes including freight and taxes, and turn the winner into a purchase order."),
    ("Staff payroll", "Monthly salaries with PF, ESI and professional tax for site staff."),
    ("Reports library", "Over 50 ready reports as PDF or Excel, plus a personal dashboard of the figures each person cares about."),
    ("Site roles and access", "Each person sees only the sites they are on; owners see everything."),
    ("Ask FieldOS assistant", "An in-app AI assistant that answers questions about the company's own sites by chat or voice."),
    ("Indian languages", "Menus in English, Hindi, Telugu, Tamil, Kannada and Marathi; each person picks their own."),
    ("Data safety", "Only people the company invites can see its data, and they can be removed any time. Backups and account deletion are built in."),
]

STATUS_NOTES = [
    "The app is in closed testing on Google Play and launching publicly soon. New companies start with a guided pilot on one to three real sites.",
    "There is no web or desktop dashboard yet; everything is on the phone. Do not promise one.",
    "Do not name any customer, and do not quote results, savings or percentages. We have no published case studies yet.",
]

# Segment -> the pains worth opening with. The research step refines these per firm.
SEGMENT_ANGLES = {
    "developer": [
        "many towers or projects running at once with contractors on each",
        "the owner or COO not knowing which site is slipping until the monthly review",
        "delivery and bill disputes with suppliers and contractors",
        "RERA progress and documentation",
    ],
    "contractor": [
        "Saturday wage disputes and advances paid twice",
        "cement and steel deliveries short against the PO",
        "supervisors' expenses without bills",
        "running-account bills and measurement records for the client",
    ],
    "architecture": [
        "site supervision reports to clients",
        "progress photos and issue tracking across client sites",
        "recommending a simple tool to the contractors they supervise",
    ],
    "home construction": [
        "keeping the home owner updated with photos and progress",
        "labour and material spend per house",
    ],
}

GOAL = (
    "Book a 30-minute site walkthrough or demo with the decision maker (owner, director, COO or "
    "head of projects). A demo booking is a win. Never try to close a sale on the call."
)

PRICE_DEFLECTION = {
    "en": "Fair question! It really depends on how many sites and people you run, so our team gives a written proposal after a short site walkthrough. Shall I set that up?",
    "hi": "अच्छा सवाल है जी। यह आपकी sites और team के size पर depend करता है, इसलिए हमारी team एक छोटे site walkthrough के बाद written proposal देती है। Walkthrough fix कर दें?",
    "te": "మంచి ప్రశ్న అండి. అది మీ sites, team size మీద depend అవుతుంది, అందుకే మా team చిన్న site walkthrough తర్వాత written proposal ఇస్తుంది. Walkthrough fix చేయమంటారా?",
}

KNOWLEDGE_TEXT = "\n".join(
    [f"Company: {COMPANY['name']}, {COMPANY['city']}. Email {COMPANY['email']}. Website {COMPANY['website']}.",
     f"Product: {PRODUCT_ONE_LINER}", "", "Features you may mention (only these):"]
    + [f"- {name}: {why}" for name, why in FEATURES]
    + ["", "Status and honesty notes:"] + [f"- {n}" for n in STATUS_NOTES]
    + ["", f"Goal of every conversation: {GOAL}"]
)
