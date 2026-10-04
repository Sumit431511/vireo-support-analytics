# Validation evidence

Run against the supplied files on 4 October 2026 using the implemented preprocessing and metric engine.

## Deterministic results

| Check | Result |
|---|---:|
| Tickets loaded | 11,750 |
| Roster agents | 44 |
| Rated tickets | 5,196 |
| CSAT response rate | 44.22% |
| Overall CSAT | 3.3266 / 5 |
| Overall AHT | 1,646.85 minutes |
| First-response breaches | 1,064 |
| Legacy records normalized | 3,374 |
| Tier 1 evidence threshold (unfiltered) | 93 rated tickets |
| Tier 1 agents eligible for score | 28 |
| Training-review candidates returned | 10 |

The PRD reference trend values reconcile after rounding: October 2025 CSAT is 3.602, December 2025 is 3.290, and June 2026 is 3.402.

## Source-data checks

| Check | Result | Treatment |
|---|---:|---|
| Duplicate ticket IDs | 0 | Pass |
| Missing/unknown agent IDs | 0 / 0 | Pass; join is `agent_id` only |
| Invalid CSAT values | 0 | Pass |
| Missing CSAT | 6,554 | Report; excluded from means |
| Missing timestamps | 567 | Report; AHT unavailable for those records |
| Missing/unknown product SKU | 0 / 0 | Pass |
| Missing/unknown nonblank order ID | 4,107 / 0 | Report / Pass; order context is optional |
| Unknown source system | 0 | Pass |
| Duplicate display-name roster rows | 2 | Report; known shared name, no name joins |
| Refund plus replacement | 6 | Report; policy escalation exception |
| Negative normalized AHT | 0 | Pass |
| Clearly unusable IVR fragments | 14 | Report; omitted only from optional AI samples |

## Independent dashboard spot checks

The app recalculates CSAT and valid AHT directly from ticket rows for three displayed agents and compares each to the agent table. A check passes only when both absolute deltas are below `1e-9`; the in-app sample passed. This is six independent metric comparisons with **0 observed mismatches (0/6)**. This is intentionally a separate aggregation path from the visual table.

## Automated verification

`python -m pytest -q` completed successfully with **21 passed** tests and **0 failures**. Streamlit's `AppTest` executed all five dashboard pages, an agent filter, a site filter, a Tier 1 filter, and the no-key AI fallback with zero exceptions. A live Streamlit server returned `200 OK` from `/_stcore/health`.

## AI validation status

No human-labelled ticket set was supplied, so AI accuracy, error rate, and common-error categories are **not reported**. The dashboard offers a 50-ticket CSV template with `ticket_id`, `human_issue_category`, and `ai_issue_category` fields. After a human labels 50–100 examples, the included `ai_validation_summary` helper can calculate accuracy and error rate without inventing results.
