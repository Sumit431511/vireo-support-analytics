from __future__ import annotations

import pandas as pd
import pytest

from src.business_impact import calculate_business_impact
from src.metrics import agent_metrics, apply_filters, filter_roster, monthly_trends, overall_metrics
from src.preprocessing import prepare_tickets


def make_tickets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticket_id": "T1", "created_at": "2025-01-01 08:00", "first_response_at": "2025-01-01 08:10",
                "resolved_at": "2025-01-01 03:40", "status": "resolved", "channel": "chat", "customer_id": "C1",
                "product_sku": "P1", "category": "Connectivity", "assigned_team": "Chat", "agent_id": "A1",
                "transfers": 0, "csat_score": 5, "replacement_issued": "N", "customer_message": "help", "agent_notes": "done", "source_system": "legacy_fd",
            },
            {
                "ticket_id": "T2", "created_at": "2025-01-01 08:00", "first_response_at": "2025-01-01 08:30",
                "resolved_at": "2025-01-01 10:30", "status": "resolved", "channel": "email", "customer_id": "C2",
                "product_sku": "P1", "category": "Connectivity", "assigned_team": "Chat", "agent_id": "A1",
                "transfers": 1, "csat_score": None, "replacement_issued": "N", "customer_message": "help", "agent_notes": "done", "source_system": "helpdesk",
            },
            {
                "ticket_id": "T3", "created_at": "2025-01-02 08:00", "first_response_at": "2025-01-02 10:01",
                "resolved_at": "2025-01-02 11:01", "status": "resolved", "channel": "voice", "customer_id": "C3",
                "product_sku": "P1", "category": "Audio Quality", "assigned_team": "Voice", "agent_id": "A2",
                "transfers": 0, "csat_score": 3, "replacement_issued": "Y", "customer_message": "help", "agent_notes": "done", "source_system": "helpdesk",
            },
        ]
    )


def make_agents() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"agent_id": "A1", "name": "One", "site": "Indore", "team": "Chat", "shift": "Day", "tier": 1},
            {"agent_id": "A2", "name": "Two", "site": "Indore", "team": "Voice", "shift": "Day", "tier": 1},
        ]
    )


def test_legacy_resolution_is_normalized_before_aht() -> None:
    prepared = prepare_tickets(make_tickets())
    # 03:40 UTC + 05:30 = 09:10 IST, one hour after first response at 08:10 IST.
    assert prepared.loc[prepared.ticket_id.eq("T1"), "aht_minutes"].iloc[0] == 60


def test_csat_excludes_blank_scores_and_aht_is_first_response_to_resolution() -> None:
    prepared = prepare_tickets(make_tickets())
    metrics = agent_metrics(prepared, make_agents()).set_index("agent_id")
    assert metrics.loc["A1", "ticket_volume"] == 2
    assert metrics.loc["A1", "rated_tickets"] == 1
    assert metrics.loc["A1", "csat"] == 5
    assert metrics.loc["A1", "csat_response_rate"] == pytest.approx(0.5)
    assert metrics.loc["A1", "aht_minutes"] == pytest.approx(90)


def test_channel_breaches_use_policy_targets() -> None:
    prepared = prepare_tickets(make_tickets()).set_index("ticket_id")
    assert bool(prepared.loc["T1", "is_breached"]) is False  # Chat: 10 minutes <= 15.
    assert bool(prepared.loc["T2", "is_breached"]) is False  # Email: 30 minutes <= 8 hours.
    assert bool(prepared.loc["T3", "is_breached"]) is True  # Voice: 121 minutes > 2 hours.


def test_monthly_and_overall_metrics_are_deterministic() -> None:
    prepared = prepare_tickets(make_tickets())
    trends = monthly_trends(prepared)
    summary = overall_metrics(prepared)
    assert len(trends) == 1
    assert trends.loc[0, "rated_tickets"] == 2
    assert summary["csat"] == pytest.approx(4.0)
    assert summary["breach_count"] == 1


def test_policy_cost_lines_are_calculated_separately() -> None:
    prepared = prepare_tickets(make_tickets())
    products = pd.DataFrame({"sku": ["P1"], "unit_cost_inr": [100]})
    impact = calculate_business_impact(prepared, products)
    assert impact["replacement_planning_cost_inr"] == 440  # Unit cost + policy logistics.
    assert impact["breach_credit_cost_inr"] == 350
    assert impact["contact_operating_cost_inr"] == 990
    assert impact["transfer_rehandling_cost_inr"] == 305


def test_tier_filter_accepts_streamlit_serialized_choices() -> None:
    prepared = prepare_tickets(make_tickets())
    filtered = apply_filters(prepared, make_agents(), tiers=["1"])
    assert set(filtered["agent_id"]) == {"A1", "A2"}


def test_roster_filter_removes_agents_outside_the_active_selection() -> None:
    roster = filter_roster(make_agents(), agent_ids=["A1"])
    assert roster["agent_id"].tolist() == ["A1"]
