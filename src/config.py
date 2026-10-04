"""Policy-backed constants and application defaults."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AI_CACHE_DIR = PROJECT_ROOT / "artifacts" / "ai_cache"

# Service targets and cost standards are from support-policy.pdf, sections 3 and 4.
BREACH_TARGET_MINUTES = {
    "chat": 15,
    "voice": 120,  # Voice callback
    "social": 240,
    "email": 480,
}
CONTACT_COST_INR = {
    "chat": 210,
    "email": 260,
    "voice": 520,
    "social": 240,
}
BREACH_CREDIT_INR = 350
TRANSFER_COST_INR = 305
REPLACEMENT_LOGISTICS_INR = 340
AGENT_HOURLY_COST_INR = 165

VALID_SOURCES = {"legacy_fd", "helpdesk"}
VALID_STATUSES = {"resolved", "closed", "open", "pending"}
VALID_TIERS = {1, 2}

# The taxonomy is supplied at runtime from the ticket-category values, so this
# fallback only covers an unavailable/ambiguous LLM response.
UNKNOWN_CATEGORY = "Unknown / Unclassified"
RESOLUTION_QUALITY_VALUES = {"complete", "incomplete", "unclear"}

DEFAULT_CSAT_WEIGHT = 0.75
DEFAULT_AHT_WEIGHT = 0.25
DEFAULT_SAMPLE_SIZE = 20
DEFAULT_CANDIDATE_CAP = 10
DEFAULT_RECOGNITION_CAP = 5

