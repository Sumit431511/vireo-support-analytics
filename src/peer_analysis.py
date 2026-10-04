"""Peer-aware comparison helpers. Tier 2 is explicitly contextual only."""

from __future__ import annotations

import math

import pandas as pd


def derive_minimum_rated_tickets(metrics: pd.DataFrame) -> int:
    """Use the Tier 1 first quartile as a documented, data-derived default."""
    values = metrics.loc[(metrics["tier"] == 1) & (metrics["rated_tickets"] > 0), "rated_tickets"]
    if values.empty:
        return 1
    return max(1, math.ceil(float(values.quantile(0.25))))


def add_peer_context(metrics: pd.DataFrame) -> pd.DataFrame:
    """Add Tier+team pooled baselines; no volume/AHT cross-tier comparison is made."""
    result = metrics.copy()
    weighted = result.copy()
    weighted["csat_points"] = weighted["csat"].fillna(0) * weighted["rated_tickets"]
    weighted["aht_points"] = weighted["aht_minutes"].fillna(0) * weighted["ticket_volume"]
    peers = (
        weighted.groupby(["tier", "team"], dropna=False)
        .agg(
            peer_rated_tickets=("rated_tickets", "sum"),
            peer_ticket_volume=("ticket_volume", "sum"),
            peer_csat_points=("csat_points", "sum"),
            peer_aht_points=("aht_points", "sum"),
        )
        .reset_index()
    )
    # Use NaN rather than nullable-object values so downstream numeric scoring
    # and Streamlit table formatting remain safe for sparse filtered cohorts.
    peers["peer_csat"] = peers["peer_csat_points"] / peers["peer_rated_tickets"].replace(0, float("nan"))
    peers["peer_aht_minutes"] = peers["peer_aht_points"] / peers["peer_ticket_volume"].replace(0, float("nan"))
    result = result.merge(
        peers[["tier", "team", "peer_csat", "peer_aht_minutes"]],
        on=["tier", "team"],
        how="left",
        validate="many_to_one",
    )
    for column in ("csat", "aht_minutes", "peer_csat", "peer_aht_minutes"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["csat_peer_gap"] = result["csat"] - result["peer_csat"]
    result["aht_peer_gap_minutes"] = result["aht_minutes"] - result["peer_aht_minutes"]
    return result
