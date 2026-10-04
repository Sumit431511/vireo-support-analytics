from __future__ import annotations

import pandas as pd

from src.flagging import score_agents, select_recognition_candidates, select_training_candidates


def sample_metrics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"agent_id": "A1", "name": "One", "site": "I", "team": "Chat", "shift": "Day", "tier": 1, "ticket_volume": 100, "rated_tickets": 50, "csat": 2.5, "aht_minutes": 180},
            {"agent_id": "A2", "name": "Two", "site": "I", "team": "Chat", "shift": "Day", "tier": 1, "ticket_volume": 100, "rated_tickets": 50, "csat": 3.0, "aht_minutes": 150},
            {"agent_id": "A3", "name": "Three", "site": "I", "team": "Chat", "shift": "Day", "tier": 1, "ticket_volume": 100, "rated_tickets": 50, "csat": 4.8, "aht_minutes": 50},
            {"agent_id": "A4", "name": "Four", "site": "I", "team": "Chat", "shift": "Day", "tier": 2, "ticket_volume": 100, "rated_tickets": 50, "csat": 1.0, "aht_minutes": 600},
            {"agent_id": "A5", "name": "Five", "site": "I", "team": "Chat", "shift": "Day", "tier": 1, "ticket_volume": 10, "rated_tickets": 2, "csat": 1.0, "aht_minutes": 800},
        ]
    )


def test_tier_two_and_insufficient_sample_are_never_padded_into_training_candidates() -> None:
    scored = score_agents(sample_metrics(), minimum_rated_tickets=10)
    candidates = select_training_candidates(scored, cap=10)
    assert len(candidates) == 3
    assert candidates["tier"].eq(1).all()
    assert "A4" not in candidates["agent_id"].tolist()
    assert "A5" not in candidates["agent_id"].tolist()
    assert scored.set_index("agent_id").loc["A4", "review_status"] == "Tier 2 - contextual, not ranked"
    assert scored.set_index("agent_id").loc["A5", "review_status"] == "Insufficient sample"


def test_recognition_is_separate_from_training_ranking() -> None:
    scored = score_agents(sample_metrics(), minimum_rated_tickets=10)
    recognition = select_recognition_candidates(scored, cap=1)
    assert recognition.iloc[0]["agent_id"] == "A3"


def test_peer_context_is_within_tier_and_team() -> None:
    scored = score_agents(sample_metrics(), minimum_rated_tickets=10).set_index("agent_id")
    # The baseline is rating-weighted across all same Tier/team observations;
    # evidence eligibility controls selection, not the reference queue mix.
    assert scored.loc["A1", "peer_csat"] == (2.5 * 50 + 3.0 * 50 + 4.8 * 50 + 1.0 * 2) / 152
    assert scored.loc["A4", "peer_csat"] == 1.0  # Tier 2 never uses the Tier 1 baseline.


def test_sparse_filter_style_peer_values_remain_numeric() -> None:
    sparse = sample_metrics().loc[lambda frame: frame["agent_id"].isin(["A1", "A4"])].copy()
    scored = score_agents(sparse, minimum_rated_tickets=10)
    assert pd.api.types.is_numeric_dtype(scored["peer_csat"])
    assert pd.api.types.is_numeric_dtype(scored["csat_peer_gap"])
