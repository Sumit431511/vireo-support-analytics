"""Transparent review and recognition candidate selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT_AHT_WEIGHT, DEFAULT_CANDIDATE_CAP, DEFAULT_CSAT_WEIGHT, DEFAULT_RECOGNITION_CAP
from .peer_analysis import add_peer_context


def _safe_zscore(values: pd.Series) -> pd.Series:
    scale = values.std(ddof=0)
    if pd.isna(scale) or scale == 0:
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / scale


def _review_reason(row: pd.Series) -> str:
    parts = [f"{int(row['rated_tickets'])} rated tickets"]
    if pd.notna(row["csat_peer_gap"]):
        direction = "below" if row["csat_peer_gap"] < 0 else "above"
        parts.append(f"CSAT {abs(row['csat_peer_gap']):.2f} points {direction} Tier {int(row['tier'])}/{row['team']} peer")
    if pd.notna(row["aht_peer_gap_minutes"]):
        direction = "above" if row["aht_peer_gap_minutes"] > 0 else "below"
        parts.append(f"AHT {abs(row['aht_peer_gap_minutes']):.0f} min {direction} peer")
    return "; ".join(parts) + ". Review flag is evidence for coaching review, not an employee-quality judgment."


def score_agents(
    metrics: pd.DataFrame,
    minimum_rated_tickets: int,
    csat_weight: float = DEFAULT_CSAT_WEIGHT,
    aht_weight: float = DEFAULT_AHT_WEIGHT,
) -> pd.DataFrame:
    """Score only eligible Tier 1 agents using transparent peer-normalized signals."""
    if csat_weight < 0 or aht_weight < 0 or (csat_weight + aht_weight) == 0:
        raise ValueError("At least one non-negative review weight is required.")
    result = add_peer_context(metrics)
    tier_one = result["tier"].eq(1)
    evidence = result["rated_tickets"].ge(minimum_rated_tickets)
    usable = result["csat"].notna() & result["aht_minutes"].notna()
    result["eligible_for_review"] = tier_one & evidence & usable
    result["csat_gap_z"] = pd.Series(np.nan, index=result.index, dtype="float64")
    result["aht_gap_z"] = pd.Series(np.nan, index=result.index, dtype="float64")
    eligible_index = result.index[result["eligible_for_review"]]
    if len(eligible_index):
        result.loc[eligible_index, "csat_gap_z"] = _safe_zscore(result.loc[eligible_index, "csat_peer_gap"])
        result.loc[eligible_index, "aht_gap_z"] = _safe_zscore(result.loc[eligible_index, "aht_peer_gap_minutes"])
    weight_total = csat_weight + aht_weight
    result["review_score"] = (
        csat_weight * -result["csat_gap_z"] + aht_weight * result["aht_gap_z"]
    ) / weight_total
    result["recognition_score"] = (
        csat_weight * result["csat_gap_z"] - aht_weight * result["aht_gap_z"]
    ) / weight_total
    result["review_status"] = "Context only"
    result.loc[result["tier"].eq(2), "review_status"] = "Tier 2 - contextual, not ranked"
    result.loc[tier_one & ~evidence, "review_status"] = "Insufficient sample"
    result.loc[tier_one & evidence & ~usable, "review_status"] = "Insufficient AHT/CSAT data"
    result["review_reason"] = ""
    result.loc[result["eligible_for_review"], "review_reason"] = result.loc[
        result["eligible_for_review"]
    ].apply(_review_reason, axis=1)
    return result


def select_training_candidates(scored: pd.DataFrame, cap: int = DEFAULT_CANDIDATE_CAP) -> pd.DataFrame:
    """Return up to the requested number; never pad with ineligible agents."""
    candidates = scored.loc[scored["eligible_for_review"]].sort_values(
        ["review_score", "csat", "rated_tickets"], ascending=[False, True, False]
    ).head(cap).copy()
    candidates["review_status"] = "Training review candidate"
    return candidates


def select_recognition_candidates(scored: pd.DataFrame, cap: int = DEFAULT_RECOGNITION_CAP) -> pd.DataFrame:
    """Separate positive recognition view using the same peer-aware evidence rule."""
    return scored.loc[scored["eligible_for_review"]].sort_values(
        ["recognition_score", "csat", "rated_tickets"], ascending=[False, False, False]
    ).head(cap).copy()
