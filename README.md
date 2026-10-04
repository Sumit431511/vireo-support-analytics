# Vireo Audio Support Performance & Training Analytics

A small Streamlit decision-support dashboard for Priya Raman's Q3 training review. It implements the PRD's policy-backed support metrics while keeping employee flags transparent, evidence-based, and non-causal.

## What it does

- Loads the supplied ticket, agent, product and order data; customer data is deliberately not loaded into the app.
- Validates data quality and reports exceptions without silently dropping tickets.
- Calculates CSAT from rated tickets only, first-response-to-resolution AHT, ticket volume, transfer/repeat-contact context, and first-response breaches.
- Converts legacy `resolved_at` UTC timestamps to IST (`+05:30`) before AHT calculations; current helpdesk timestamps are used as displayed.
- Joins the agent roster only with `agent_id` and surfaces duplicate display names as a known caveat.
- Provides monthly CSAT/AHT/volume/breach trends, an agent-performance table, a CSAT-vs-AHT scatter plot, Tier 2 context, and a separate top-five recognition view.
- Selects up to ten Tier 1 training-review candidates using configurable, peer-normalized CSAT (primary) and AHT (secondary) gaps, subject to a configurable evidence threshold.
- Shows deterministic issue categories and optional, bounded AI ticket-text classifications. AI uses structured JSON, injection-resistant prompts, a local cache, and never decides who should receive training.
- Calculates separate policy cost lines for replacements, SLA credits, contacts and transfers; it intentionally does not sum them into a misleading total.

## Supplied data inspected

| File | Rows | App use |
|---|---:|---|
| `tickets.csv` | 11,750 | Core ticket metrics and text sampling |
| `agents.csv` | 44 | Agent identity and Tier/team context |
| `products.csv` | 14 | Unit cost for replacement planning cost |
| `orders.csv` | 15,500 | Order-ID validation only |
| `customers.csv` | 9,500 | Inspected, then excluded to avoid unnecessary PII processing |
| `support-policy.pdf` | 2 pages | Authoritative metric, SLA and cost definitions |
| `email-thread.txt` | 5 messages | Budget, ranking, data-quality and queue-mix constraints |

The supplied data has 3,374 legacy tickets and 8,376 current-helpdesk tickets. It has 5,196 rated tickets (44.2% response rate). The dashboard's initial minimum-evidence default is the first quartile of positive Tier 1 rated-ticket counts: **93 rated tickets** for the unfiltered dataset. It is recomputed for filters and remains configurable; for a very sparse filtered cohort with at most one rating per agent, it is safely fixed at one.

## Setup and run

### Prerequisites

- Python 3.10 or later
- The supplied files remain in the `data/` directory
- Internet access only if you choose to use the optional AI analysis

From the project root, check Python is available:

```powershell
python --version
```

### Windows PowerShell setup

Create an isolated environment and install the exact project dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this once for the current terminal and then repeat the activation command:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Start the dashboard:

```powershell
python -m streamlit run app.py
```

Open the local address printed by Streamlit, normally <http://localhost:8501>. Stop the server with `Ctrl+C`.

### Optional: configure Groq AI analysis

The dashboard works fully without an API key; CSAT, AHT, breaches, candidate selection, and business-impact calculations are deterministic. A key only enables the optional bounded ticket-text analysis in **Training Review**.

1. Copy the provided template in the project root:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Open `.env` and replace `YOUR_API_KEY` with your Groq key. Keep the endpoint and model unless you intentionally choose another supported Groq model:

   ```dotenv
   LLM_API_KEY="gsk_your_key_here"
   LLM_BASE_URL="https://api.groq.com/openai/v1"
   LLM_MODEL="openai/gpt-oss-20b"
   ```

3. Restart Streamlit after saving `.env`:

   ```powershell
   python -m streamlit run app.py
   ```

The app loads `.env` from the project root. It never displays the key. Do not commit or submit `.env`; `.gitignore` excludes it. Process environment variables with the same names override `.env` values.

To run the AI sample, open **Training Review**, choose an eligible candidate, and select **Run / reuse cached AI sample**. It processes at most 20 non-junk tickets, validates the structured response locally, and saves reusable results under `artifacts/ai_cache/`. No LLM call is made until that button is selected.

### Verify the installation

Run the automated checks before use or submission:

```powershell
python -m pytest -q
```

Expected result: all tests pass. To verify the web app manually, start it, open each sidebar page once, and confirm the **Data & Validation** page has no failed deterministic checks.

## Metric and review methodology

| Metric | Implementation |
|---|---|
| CSAT | Mean of nonblank `csat_score` values only; blanks are not zero. |
| AHT | `resolved_at_ist - first_response_at`; legacy resolution timestamps receive `+05:30` first. Negative values are reported and omitted from averages. |
| First-response breach | `first_response_at - created_at` greater than policy channel target: chat 15m, voice 2h, social 4h, email 8h. |
| Volume | `count(ticket_id)`, always displayed with rated volume and response rate. |
| Peer group | Ticket/rating-weighted baseline within the same `tier + team`. |
| Review score | 75% normalized negative CSAT peer gap + 25% normalized positive AHT peer gap, with configurable weights. |
| Eligibility | Tier 1, configurable minimum rated tickets, and usable CSAT/AHT. Tier 2 is contextual only. |

The score identifies review priorities, not poor performers or causal explanations. Transfers and repeat contacts are displayed as operational context rather than employee-quality inputs.

## Business cost lines

All values come from the support policy:

- Replacement planning cost = product unit cost from `products.csv` + ₹340 logistics, per issued replacement.
- SLA credits = ₹350 per first-response breach.
- Contact operating cost = the channel-specific policy cost (chat ₹210, email ₹260, voice ₹520, social ₹240) per ticket/contact.
- Transfer re-handling cost = ₹305 per transfer.

These lines are not combined, since doing so could double count a ticket or imply an unsupported saving opportunity.

## Quantified management goal

For the next Q3 operating review, target a first-response breach rate of **7.0%**, down from the observed **9.72%** in April-June 2026. At the same 2,067-ticket quarterly volume, this is approximately **56 fewer breached tickets** and **₹19,700 less in policy-mandated ₹350 SLA credits per quarter**. This is a management planning scenario, not a claim that training alone will cause the reduction or that the savings can be combined with other cost lines.

## Validation and tests

Run the automated suite with:

```powershell
python -m pytest -q
```

The suite covers CSAT, AHT, legacy time normalization, breaches, Tier 2 exclusion, candidate selection, supplied-data integrity, structured AI validation, malformed output, timeout handling, unknown categories, and prompt-injection handling. See [validation.md](docs/validation.md) for the actual source-data checks and spot-check results.

AI accuracy is intentionally not reported: no human-labelled 50–100 ticket validation set was supplied. The dashboard provides a 50-ticket validation-template download so a human review can create one before an accuracy/error-rate claim is made.

## Project layout

```text
app.py                         Streamlit UI
src/                           loading, validation, preprocessing, metrics, scoring, AI and cost modules
tests/                         deterministic and AI resilience tests
artifacts/ai_cache/            local structured AI-result cache (created on demand)
docs/validation.md             actual validation evidence
docs/memo.md                   one-page executive memo
docs/demo-script.md            concise three-minute demo guide
docs/ai-usage.md               AI/tool, cost, prompt, and scope disclosure
submission-form.md             completed replacement form (original template was absent)
artifacts/vireo_dashboard_walkthrough.mp4  1:59 captioned dashboard walkthrough
```

## Scope and limitations

- The data includes 567 missing resolution timestamps, so those records have no AHT; the app reports rather than fabricates values.
- It reports 6 tickets with both a refund amount and a replacement, which policy says should be escalated; it does not “repair” source records.
- Failed-IVR detection excludes only clearly unusable fragments from optional AI sampling. A normal IVR transcript may remain meaningful.
- Full order analytics, customer segmentation, predictive modelling, custom ML, a production API, and per-ticket LLM processing are intentionally outside this five-hour MVP.
- No supplied human AI labels were available, so no AI accuracy/error-rate claim is made. A 50-ticket validation template is provided. The original submission-form template was absent from the pack; `submission-form.md` transparently records the required responses instead.
