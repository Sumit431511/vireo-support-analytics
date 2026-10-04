# AI and tool disclosure

## Tools used

- OpenAI Codex was used to implement and test this MVP.
- The dashboard contains an optional OpenAI-compatible classification client. It loads `LLM_API_KEY`, `LLM_MODEL`, and optional `LLM_BASE_URL` from the process environment or project-root `.env` file (process values take precedence). It is compatible with Groq and other user-supplied OpenAI-compatible providers.
- Pandas performs all arithmetic, eligibility, peer comparison, and candidate selection. An LLM never performs those decisions.

## Live model use and cost

No live LLM credentials were supplied for this delivery. Therefore the delivered cache contains no live classifications, the dashboard made **0** live ticket-classification calls during verification, and the dashboard LLM API cost was **₹0**. The automated AI tests use a local mock response and do not call a provider.

The optional workflow caps a run at 20 non-junk tickets for one selected candidate and caches each validated JSON result in `artifacts/ai_cache/`. Cost therefore depends on the user-selected provider/model and cannot be truthfully estimated here without a supplied price and credentials.

For Groq, set `LLM_BASE_URL=https://api.groq.com/openai/v1` and a Groq-supported `LLM_MODEL` such as `openai/gpt-oss-20b`. The client labels this configuration in the dashboard but never displays the secret value. Changing provider URL also changes the cache key, so one provider's response is not reused as another's.

## Prompt and safety choices

Prompt V1 was basic classification. V2 introduced the actual supplied ticket-category taxonomy and JSON-only output. V3 added the untrusted-data rule, uncertainty handling, resolution quality, and a prohibition on employee judgments. The active V3 prompt is visible in the app's **Data & Validation** page.

## Deliberately discarded

- Per-ticket LLM analysis of all 11,750 records: expensive and outside the cost-control requirement.
- Full order/customer analytics: unnecessary customer-data processing for the Q3 training decision.
- Predictive modelling, custom ML, production API, and automated HR outcomes: not needed for an explainable five-hour MVP.

