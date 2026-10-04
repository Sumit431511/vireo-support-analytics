"""Explicit data-quality and independent metric validation checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .config import VALID_SOURCES


@dataclass(frozen=True)
class ValidationCheck:
    check: str
    status: str
    count: int
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    checks: tuple[ValidationCheck, ...]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([check.__dict__ for check in self.checks])

    @property
    def failures(self) -> int:
        return sum(check.status == "Fail" for check in self.checks)


def _status(count: int, failure: bool = True) -> str:
    if count == 0:
        return "Pass"
    return "Fail" if failure else "Report"


def validate_data(
    tickets: pd.DataFrame,
    agents: pd.DataFrame,
    products: pd.DataFrame,
    orders: pd.DataFrame,
    prepared_tickets: pd.DataFrame | None = None,
) -> ValidationReport:
    """Report quality exceptions rather than silently dropping source records."""
    checks: list[ValidationCheck] = []
    duplicate_tickets = int(tickets["ticket_id"].duplicated().sum())
    missing_agent = int(tickets["agent_id"].isna().sum())
    unknown_agent = int((~tickets["agent_id"].isin(agents["agent_id"]) & tickets["agent_id"].notna()).sum())
    csat_numeric = pd.to_numeric(tickets["csat_score"], errors="coerce")
    invalid_csat = int((tickets["csat_score"].notna() & ~csat_numeric.between(1, 5)).sum())
    missing_csat = int(tickets["csat_score"].isna().sum())
    missing_timestamps = int(tickets[["created_at", "first_response_at", "resolved_at"]].isna().any(axis=1).sum())
    missing_sku = int(tickets["product_sku"].isna().sum())
    unknown_sku = int((tickets["product_sku"].notna() & ~tickets["product_sku"].isin(products["sku"])).sum())
    missing_order = int(tickets["order_id"].isna().sum())
    unknown_order = int((tickets["order_id"].notna() & ~tickets["order_id"].isin(orders["order_id"])).sum())
    unknown_source = int((~tickets["source_system"].isin(VALID_SOURCES)).sum())
    duplicate_names = int(agents["name"].duplicated(keep=False).sum())
    refund_and_replacement = int((tickets["refund_amount_inr"].notna() & tickets["replacement_issued"].eq("Y")).sum())
    checks.extend(
        [
            ValidationCheck("Duplicate ticket IDs", _status(duplicate_tickets), duplicate_tickets, "ticket_id must be unique"),
            ValidationCheck("Missing agent IDs", _status(missing_agent), missing_agent, "records are retained and reported"),
            ValidationCheck("Unknown agent IDs", _status(unknown_agent), unknown_agent, "join is performed only on agent_id"),
            ValidationCheck("Invalid CSAT values", _status(invalid_csat), invalid_csat, "valid values are 1 through 5"),
            ValidationCheck("Missing CSAT responses", _status(missing_csat, False), missing_csat, "excluded from CSAT averages; not zero"),
            ValidationCheck("Missing timestamps", _status(missing_timestamps, False), missing_timestamps, "AHT unavailable where a timestamp is missing"),
            ValidationCheck("Missing product SKU", _status(missing_sku, False), missing_sku, "reported for replacement-cost coverage"),
            ValidationCheck("Unknown product SKU", _status(unknown_sku), unknown_sku, "product-cost join cannot be made"),
            ValidationCheck("Missing order IDs", _status(missing_order, False), missing_order, "order context is optional in this MVP"),
            ValidationCheck("Unknown nonblank order IDs", _status(unknown_order), unknown_order, "nonblank IDs must join to orders.csv"),
            ValidationCheck("Unknown source system", _status(unknown_source), unknown_source, "only legacy_fd and helpdesk are expected"),
            ValidationCheck("Duplicate display-name roster rows", _status(duplicate_names, False), duplicate_names, "expected caveat: joins use agent_id, never name"),
            ValidationCheck("Refund + replacement on one ticket", _status(refund_and_replacement, False), refund_and_replacement, "policy exception requiring escalation"),
        ]
    )
    if prepared_tickets is not None:
        invalid_ordering = int((prepared_tickets["aht_minutes"] < 0).sum())
        junk_ivr = int(prepared_tickets["is_junk_ivr"].sum())
        checks.extend(
            [
                ValidationCheck("Negative normalized AHT", _status(invalid_ordering), invalid_ordering, "after legacy UTC-to-IST normalization"),
                ValidationCheck("Clearly junk IVR fragments", _status(junk_ivr, False), junk_ivr, "excluded from optional AI sampling only"),
            ]
        )
    return ValidationReport(tuple(checks))


def independent_metric_checks(
    prepared_tickets: pd.DataFrame, agent_metrics: pd.DataFrame, sample_size: int = 3
) -> pd.DataFrame:
    """Recompute a small agent sample directly from ticket rows for dashboard QA."""
    candidates = agent_metrics.loc[agent_metrics["ticket_volume"] > 0, "agent_id"].head(sample_size)
    rows: list[dict[str, object]] = []
    for agent_id in candidates:
        subset = prepared_tickets.loc[prepared_tickets["agent_id"].eq(agent_id)]
        direct_csat = subset["csat_score"].mean()
        direct_aht = subset.loc[subset["aht_minutes"].ge(0), "aht_minutes"].mean()
        shown = agent_metrics.loc[agent_metrics["agent_id"].eq(agent_id)].iloc[0]
        csat_delta = abs(direct_csat - shown["csat"])
        aht_delta = abs(direct_aht - shown["aht_minutes"])
        rows.append(
            {
                "agent_id": agent_id,
                "direct_csat": direct_csat,
                "dashboard_csat": shown["csat"],
                "direct_aht_minutes": direct_aht,
                "dashboard_aht_minutes": shown["aht_minutes"],
                "csat_delta": csat_delta,
                "aht_delta": aht_delta,
                "result": "Pass" if csat_delta < 1e-9 and aht_delta < 1e-9 else "Fail",
            }
        )
    return pd.DataFrame(rows)

