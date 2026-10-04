"""Deterministic ticket, trend, and agent metrics."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def filter_roster(
    agents: pd.DataFrame,
    sites: Iterable[str] | None = None,
    teams: Iterable[str] | None = None,
    shifts: Iterable[str] | None = None,
    tiers: Iterable[int] | None = None,
    agent_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Return roster rows in the active UI context, always keyed by agent_id."""
    result = agents.copy()
    for column, selected in (("site", sites), ("team", teams), ("shift", shifts), ("tier", tiers), ("agent_id", agent_ids)):
        if selected:
            if column == "tier":
                selected = [int(value) for value in selected]
            result = result.loc[result[column].isin(selected)]
    return result.copy()


def apply_filters(
    tickets: pd.DataFrame,
    agents: pd.DataFrame,
    start_date: object | None = None,
    end_date: object | None = None,
    sites: Iterable[str] | None = None,
    teams: Iterable[str] | None = None,
    shifts: Iterable[str] | None = None,
    tiers: Iterable[int] | None = None,
    agent_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter by ticket-created date and agent roster attributes, never by name."""
    roster_fields = agents[["agent_id", "site", "team", "shift", "tier"]].drop_duplicates("agent_id")
    result = tickets.merge(roster_fields, on="agent_id", how="left", validate="many_to_one")
    if start_date is not None:
        result = result.loc[result["created_at_dt"].dt.date >= pd.Timestamp(start_date).date()]
    if end_date is not None:
        result = result.loc[result["created_at_dt"].dt.date <= pd.Timestamp(end_date).date()]
    for column, selected in (("site", sites), ("team", teams), ("shift", shifts), ("tier", tiers), ("agent_id", agent_ids)):
        if selected:
            if column == "tier":
                # Streamlit may serialise numeric multiselect choices as strings.
                selected = [int(value) for value in selected]
            result = result.loc[result[column].isin(selected)]
    return result.copy()


def agent_metrics(tickets: pd.DataFrame, agents: pd.DataFrame) -> pd.DataFrame:
    """Compute policy metrics at agent level; blanks are excluded from CSAT means."""
    grouped = tickets.groupby("agent_id", dropna=False)
    base = grouped.agg(
        ticket_volume=("ticket_id", "count"),
        rated_tickets=("csat_score", "count"),
        csat=("csat_score", "mean"),
        aht_minutes=("aht_minutes", lambda value: value[value.ge(0)].mean()),
        breach_count=("is_breached", "sum"),
        transfers=("transfers", "sum"),
        repeat_contacts=("is_repeat_contact", "sum"),
        replacement_count=("replacement_issued", lambda value: int(value.eq("Y").sum())),
    ).reset_index()
    base["csat_response_rate"] = base["rated_tickets"] / base["ticket_volume"]
    base["breach_rate"] = base["breach_count"] / base["ticket_volume"]
    roster = agents[["agent_id", "name", "site", "team", "shift", "tier"]].drop_duplicates("agent_id")
    result = roster.merge(base, on="agent_id", how="left", validate="one_to_one")
    numeric_columns = [
        "ticket_volume", "rated_tickets", "breach_count", "transfers", "repeat_contacts", "replacement_count"
    ]
    result[numeric_columns] = result[numeric_columns].fillna(0)
    result["csat_response_rate"] = result["csat_response_rate"].fillna(0)
    result["breach_rate"] = result["breach_rate"].fillna(0)
    return result


def monthly_trends(tickets: pd.DataFrame) -> pd.DataFrame:
    """Monthly trend calculations use ticket-created month and valid AHT rows."""
    result = (
        tickets.groupby("month", dropna=False)
        .agg(
            ticket_volume=("ticket_id", "count"),
            rated_tickets=("csat_score", "count"),
            csat=("csat_score", "mean"),
            aht_minutes=("aht_minutes", lambda value: value[value.ge(0)].mean()),
            breach_count=("is_breached", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )
    result["csat_response_rate"] = result["rated_tickets"] / result["ticket_volume"]
    result["breach_rate"] = result["breach_count"] / result["ticket_volume"]
    return result


def overall_metrics(tickets: pd.DataFrame) -> dict[str, float | int]:
    """Return dashboard KPI metrics with numerators available in the tables."""
    total = len(tickets)
    rated = int(tickets["csat_score"].count())
    valid_aht = tickets.loc[tickets["aht_minutes"].ge(0), "aht_minutes"]
    return {
        "total_tickets": total,
        "rated_tickets": rated,
        "csat": float(tickets["csat_score"].mean()) if rated else float("nan"),
        "aht_minutes": float(valid_aht.mean()) if not valid_aht.empty else float("nan"),
        "csat_response_rate": rated / total if total else 0.0,
        "breach_count": int(tickets["is_breached"].sum()),
    }


def issue_breakdown(tickets: pd.DataFrame) -> pd.DataFrame:
    """Use supplied ticket categories for a transparent, complete issue breakdown."""
    result = (
        tickets.groupby("category", dropna=False)
        .agg(tickets=("ticket_id", "count"), csat=("csat_score", "mean"))
        .reset_index()
        .sort_values("tickets", ascending=False)
    )
    result["share"] = result["tickets"] / result["tickets"].sum() if len(tickets) else 0
    return result
