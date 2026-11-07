# Market research: growing Sangam from 1 vertical to 20

Date: 2026-11-07. Extends [`market_research/vertical_analysis_report.md`](../../market_research/vertical_analysis_report.md) (12 verticals, July 2026).

## 1. How much to trust this

| Kind of claim | Status |
|---|---|
| Regulatory deadlines (Schedule M, DPDP) | Checked against several news and law-firm sources (links below). **Not** checked against the official gazette text. Verify before quoting externally. |
| Competitor and pricing facts | Mostly **not findable**. Vendors quote privately. Where the older repo docs state a number, it is flagged. |
| Market-size numbers | Paid-report and media figures that disagree with each other. Treat as orders of magnitude only. |
| Scores for verticals 13-20 | **My judgment** applying the existing rubric. Not evidence. Validate with customer calls (section 6). |
| Regulator names | Standard, well-known Indian bodies, from general knowledge, not web-verified. |

## 2. What the search actually established

**Pharma has a real, dated forcing function.** The revised Schedule M (GMP) applied to larger units from 1 Jan 2025. Units under ₹250 crore turnover, roughly 8,500 of them, were given until 31 Dec 2025. Reporting in Jan 2026 said an extension was unlikely, and only about 26% of eligible MSMEs had filed upgrade plans by the deadline. CDSCO ordered GMP compliance from 1 Jan 2026 after the cough-syrup deaths, with inspections to follow. I found **no official notice of the position as of Nov 2026**, so confirm current enforcement. Sources: [Business Standard](https://www.business-standard.com/industry/news/schedule-m-extension-for-msme-pharma-firms-unlikely-125122901058_1.html), [Business Today](https://www.businesstoday.in/latest/corporate/story/comply-with-global-practices-by-jan-1-or-shut-shop-cdsco-to-pharma-manufacturers-after-cough-syrup-deaths-501498-2025-11-10), [Medical Dialogues](https://medicaldialogues.in/news/industry/pharma/cdsco-dop-told-to-find-workable-solution-on-revised-schedule-m-gmp-concerns-162969).

**DPDP applies to Sangam itself.** The DPDP Rules were notified 13 Nov 2025 with an 18-month rollout; most duties apply from about **13 May 2027**. A voice terminal that records operators is collecting personal data, so consent, retention and breach handling (a 72-hour breach notice is reported) become product requirements within the horizon of this plan. Sources: [YourStory](https://yourstory.com/2025/11/digital-personal-data-protection-dpdp-rules-2025-rollout-over-18-months), [AZB](https://www.azbpartners.com/bank/indias-digital-personal-data-protection-act-phased-rollout-and-key-compliance-milestones/). Sources disagree slightly on dates.

**The mid-market gap is plausible but not proven.** G2 data shows about 78% of Veeva Vault QMS reviewers are enterprise and 22% mid-market, and Veeva publishes no price. Named mid-market alternatives: ZenQMS, QT9, Qualityze, SimplerQMS, MasterControl, Qualio, TrackWise, Kneat. None is evidenced as India-specific or CDSCO-validated, which is the opening. Sources: [G2](https://www.g2.com/compare/kneat-gx-vs-veeva-vault-qms), [ERP Research](https://erpresearch.com/erp-add-ons/healthcare/veeva-vault-qms).

**Vertical SaaS in India is growing faster than horizontal.** Inc42 projects vertical SaaS going from about $5B to $26B in six years, against horizontal $9B to $44B. A paid report puts total India SaaS at about $11.6B in 2026 and calls manufacturing under-served. Methodology is unverified. Sources: [Inc42](https://inc42.com/features/india-saas-startups-market-opportunity-2030-trends), [ReportCubes](https://www.thereportcubes.com/report-store/software-as-a-service-market-india).

**Construction's payment hook is statutory.** RERA requires 70% of allottee collections in a project account. Niche tools already exist ([ReraDesk](https://reradesk.pages.dev/features/escrow-monitoring.html)) and banks sell 70:30 RERA accounts ([HDFC](https://www.hdfc.bank.in/current-accounts/rera-current-account)). One page claimed 75%; I treat that as wrong. Penalty figures conflict across sources.

**Voice coverage is uneven.** Sarvam lists speech-to-text for 22 Indian languages, but one summary of its docs says the Bulbul v3 text-to-speech covers only **11**. Sangam's "read the decision back in the operator's language" safeguard therefore works in fewer languages than it can listen in. Prices in the results conflicted; use [Sarvam's pricing page](https://docs.sarvam.ai/api/pricing).

## 3. Problems in the existing research

1. **The `rank` column contradicts the scores.** By score the order is Pharma 90, Construction 87, Renewable EPC 86, Chemicals 85, Export 85, Food 84, Defense 84, Medical Devices 82, Logistics 82, Auto 81, Agri-inputs 80, Textile 74. The CSV ranks Food 2nd and Chemicals 3rd with lower scores than Construction (4th).
2. **"Veeva starts at +/yr"** in the report has a missing number, and my search found no public Veeva price. The claim is unsupported.
3. **"TAM ~10,000 units", "₹20-50L/yr budget"** carry no source. The only corroborated figure is ~8,500 MSME units affected by the Schedule M deadline.
4. The report is dated July; the Schedule M deadline passed after it.

## 4. The 20 verticals

Rows 1-12 use the existing rubric score, re-sorted. Rows 13-20 are tiered A/B/C by my judgment. "Reuse" is how much of the pharma pack (document types, approval matrices, escrow flows, condition vocabulary) carries over: High, Med, Low.

| # | Vertical | Score / tier | Anchor regulators | Payment hook | Reuse | Wave |
|---|---|---|---|---|---|---|
| 1 | Pharmaceutical manufacturing | 90 | CDSCO, State FDA, NPPA | C&F escrow, tender milestones | n/a (base) | 0 |
| 2 | Construction and real estate | 87 | RERA, municipal | 70% RERA account, milestones | Low | 2 |
| 3 | Renewable energy EPC | 86 | MNRE, DISCOMs | Milestone, subsidy-linked | Med | 2 |
| 4 | Specialty chemicals | 85 | CPCB/SPCB, PESO | Hazardous-goods escrow | High | 1 |
| 5 | Export-oriented manufacturing | 85 | DGFT, Customs | LC, forex | Med | 2 |
| 6 | Food processing / FMCG | 84 | FSSAI, Legal Metrology | Co-packer milestones | High | 1 |
| 7 | Defense and aerospace | 84 | DGQA, DPSU | Milestone | Low | 3 |
| 8 | Medical devices | 82 | CDSCO (MDR) | Distributor escrow | **High** | 1 |
| 9 | Pharma/food cold-chain logistics | 82 | CDSCO, FSSAI | Per-trip settlement | High | 1 |
| 10 | Auto components | 81 | BIS, OEM audits | OEM milestones | Med | 2 |
| 11 | Agri-inputs (fertilisers, pesticides) | 80 | CIB&RC, FCO | Dealer credit | Med | 3 |
| 12 | Textile and apparel | 74 | Textile Commissioner | Buyer LCs | Low | 3 |
| 13 | Hospitals and diagnostics | A | NABH, clinical-establishment acts | Insurer/TPA settlement | Med | 3 |
| 14 | Government works and PSU procurement | A | GeM, PWD/CPWD, GFR | Stage payments | Med (GovStack already built) | 3 |
| 15 | Ports, customs and freight forwarding | B | CBIC, DGFT | Demurrage, duties | Med | 2 |
| 16 | Agri commodities and warehousing | B | WDRA, APMC | e-warehouse receipts | Low | 3 |
| 17 | Mining and minerals | B | IBM, DGMS, State mining | Royalty, DMF | Low | 3 |
| 18 | Waste and water utilities | B | CPCB, ULBs | Contract milestones | Med | 3 |
| 19 | Telecom and fibre infrastructure | C | DoT right-of-way | Rollout milestones | Low | 3 |
| 20 | Education institutions | C | UGC, AICTE, NAAC | Fee cycles | Low | 3 |

## 5. Recommended order

- **Wave 0 (now): pharma.** The only vertical with a dated, enforced deadline in the evidence. The product already has CDSCO licence extraction and escrow release. Make it work end to end before widening.
- **Wave 1: medical devices, food/FMCG, specialty chemicals, cold-chain.** Shared document types and approval shapes, so most of the pack carries over. The cheapest evidence that the "one core, many packs" architecture works.
- **Wave 2: construction, renewable EPC, export, auto, ports.** Payment- and milestone-heavy. They stress the escrow engine, so fix the money path (see the code review) first.
- **Wave 3: the rest.** New regulators and little reuse. Each needs a pilot customer before any build.

Honest risk: going from 1 to 20 verticals is a sales and domain-knowledge problem more than a code problem. Each pack needs someone who knows that regulator's paperwork.

## 6. What to validate next (before building anything beyond Wave 1)

1. Five customer calls per Wave 1 vertical. Ask what they pay today, who signs, and what an audit failure costs.
2. Real willingness-to-pay. The ₹20-50L/yr figure is unsourced.
3. Which of my A/B/C tier judgments for rows 13-20 survive contact with a buyer.
4. Whether regulators expose APIs or only portals; this decides adapter cost per pack.
5. DPDP consent and retention design for voice recordings, before the May 2027 deadline.
