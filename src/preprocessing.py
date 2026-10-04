"""Timestamp normalization and safe derived ticket fields."""

from __future__ import annotations

import re

import pandas as pd

from .config import BREACH_TARGET_MINUTES


# Narrow markers for failed IVR content. A normal IVR transcript can still be a
# meaningful customer message, so it is not automatically discarded.
JUNK_IVR_MARKERS = ("[inaudible]", "[crosstalk]", "[line dropped]")


def is_junk_ivr(message: object) -> bool:
    """Detect clearly unusable IVR fragments without rejecting all voice text."""
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    return "[ivr transcript]" in lowered and any(marker in lowered for marker in JUNK_IVR_MARKERS)


def _add_repeat_contact_flag(tickets: pd.DataFrame) -> pd.DataFrame:
    """Flag a same-customer, same-category contact within 30 days of a completion."""
    result = tickets.copy()
    result["is_repeat_contact"] = False
    completed = result.loc[
        result["status"].isin(["resolved", "closed"]) & result["resolved_at_ist"].notna(),
        ["customer_id", "category", "created_at_dt", "resolved_at_ist"],
    ].copy()
    if completed.empty:
        return result

    completed["ticket_index"] = completed.index
    completed = completed.sort_values(["customer_id", "category", "created_at_dt"])
    prior_resolution = completed.groupby(["customer_id", "category"], dropna=False)["resolved_at_ist"].shift()
    interval = completed["created_at_dt"] - prior_resolution
    result.loc[completed["ticket_index"], "is_repeat_contact"] = interval.between(
        pd.Timedelta(0), pd.Timedelta(days=30), inclusive="both"
    ).to_numpy()
    return result


def prepare_tickets(tickets: pd.DataFrame) -> pd.DataFrame:
    """Apply policy timestamp rules and create deterministic diagnostic fields.

    The exported timestamp strings are treated as displayed IST except legacy
    resolution timestamps, which policy/PRD require us to reconstruct from UTC
    by adding 05:30 before AHT is calculated.
    """
    result = tickets.copy()
    for column in ("created_at", "first_response_at", "resolved_at"):
        result[f"{column}_dt"] = pd.to_datetime(result[column], errors="coerce")

    result["resolved_at_ist"] = result["resolved_at_dt"]
    legacy = result["source_system"].eq("legacy_fd")
    result.loc[legacy, "resolved_at_ist"] = (
        result.loc[legacy, "resolved_at_dt"] + pd.Timedelta(hours=5, minutes=30)
    )
    result["aht_minutes"] = (
        result["resolved_at_ist"] - result["first_response_at_dt"]
    ).dt.total_seconds() / 60
    result["first_response_minutes"] = (
        result["first_response_at_dt"] - result["created_at_dt"]
    ).dt.total_seconds() / 60
    result["breach_target_minutes"] = result["channel"].map(BREACH_TARGET_MINUTES)
    result["is_breached"] = (
        result["first_response_minutes"] > result["breach_target_minutes"]
    )
    result["is_junk_ivr"] = result["customer_message"].map(is_junk_ivr)
    result["month"] = result["created_at_dt"].dt.to_period("M").astype("string")
    result["csat_score"] = pd.to_numeric(result["csat_score"], errors="coerce")
    result["transfers"] = pd.to_numeric(result["transfers"], errors="coerce").fillna(0)
    result["replacement_issued"] = result["replacement_issued"].fillna("N")
    return _add_repeat_contact_flag(result)


def redact_ticket_text(text: object) -> str:
    """Remove common direct identifiers before an opt-in dashboard drill-down."""
    if not isinstance(text, str):
        return ""
    redacted = re.sub(r"\bVR\d{5,}\b", "[order]", text, flags=re.IGNORECASE)
    redacted = re.sub(r"\b\d{10}\b", "[phone]", redacted)
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", redacted)
    return redacted

