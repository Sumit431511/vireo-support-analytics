# Vireo Audio Task 1 - Submission Form

> The original `submission-form.md` was not present in the supplied data pack. This replacement records every deliverable and decision required by the brief without pretending to reproduce an unknown template.

## Submission

- **Project:** Vireo Audio Support Tickets (Set B)
- **Deliverable:** Streamlit support-performance and training-review dashboard
- **Start command:** `streamlit run app.py`
- **Setup instructions:** [README.md](README.md)
- **Source code:** `app.py`, `src/`, and `tests/`

## Business goal

Reduce first-response breaches from the observed 9.72% in April-June 2026 to a 7.0% management target in the next comparable quarter. At 2,067 tickets, this represents about 56 fewer policy-mandated ₹350 credits, or approximately ₹19,700 per quarter. This is a planning scenario, not a promise that training causes the outcome.

## What the tool delivers

- Policy-defined CSAT, normalized AHT, ticket volume and first-response breach calculations.
- Agent-level metrics and transparent Tier + team peer context.
- Up to ten evidence-backed Tier 1 training-review candidates; Tier 2 is contextual rather than ranked.
- Trends, CSAT-vs-AHT comparison, deterministic issue breakdowns, cost lines, and validation evidence.
- Optional cached, structured AI issue/resolution analysis on at most 20 non-junk tickets for a selected candidate.

## Validation

- 21 automated tests passed with 0 failures, including calculations, joins, timestamp normalization, candidate eligibility, AI output validation/caching/failure handling, UI filters, and sparse-cohort handling. Independent CSAT/AHT spot checks: 0 mismatches across 6 comparisons.
- Streamlit smoke tests loaded all pages and a live server health check returned `200 OK`.
- Data quality exceptions are visible in the dashboard and documented in [docs/validation.md](docs/validation.md).
- AI accuracy/error rate is not reported because no human-labelled validation set or live model credential was supplied. The dashboard provides a 50-ticket validation template instead of inventing a result.

## AI, cost, and scope disclosure

See [docs/ai-usage.md](docs/ai-usage.md). Live dashboard API calls during verification: 0. Live dashboard LLM API cost: ₹0.

## Documents and recording

- One-page non-technical memo: [docs/memo.md](docs/memo.md)
- Recording script: [docs/demo-script.md](docs/demo-script.md)
- Screen recording: `artifacts/vireo_dashboard_walkthrough.mp4` (created after live dashboard verification)

## Assumptions and exclusions

- Legacy resolution timestamps are UTC and receive the policy-required +05:30 normalization before AHT.
- Missing CSAT is no response, not zero.
- The training-review flag is decision support, not an employee-quality judgment.
- No full order/customer analytics, per-ticket LLM processing, predictive model, production API, or automated HR action was built; these are outside the five-hour MVP decision scope.
