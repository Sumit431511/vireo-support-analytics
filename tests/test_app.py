from __future__ import annotations

from datetime import date

from streamlit.testing.v1 import AppTest

from src.data_loader import load_data
from src.preprocessing import prepare_tickets

def test_sparse_filtered_cohort_does_not_render_an_invalid_minimum_slider() -> None:
    """Regression test for StreamlitInvalidMinMaxError when max rated tickets is one."""
    app = AppTest.from_file("app.py")
    app.run(timeout=60)
    app.sidebar.date_input[0].set_value((date(2025, 1, 1), date(2025, 1, 1))).run(timeout=60)

    assert not app.exception
    slider_labels = [slider.label for slider in app.sidebar.slider]
    assert "Minimum rated tickets" not in slider_labels


def test_agent_selection_filters_executive_kpis_and_agent_table() -> None:
    tickets = prepare_tickets(load_data().tickets)
    expected_ticket_count = int(tickets["agent_id"].eq("A3001").sum())
    app = AppTest.from_file("app.py")
    app.run(timeout=60)
    app.sidebar.multiselect[4].set_value(["A3001"]).run(timeout=60)

    assert not app.exception
    total_ticket_metric = next(metric for metric in app.metric if metric.label == "Total tickets")
    assert total_ticket_metric.value == f"{expected_ticket_count:,}"

    app.radio[0].set_value("Agent Performance").run(timeout=60)
    agent_table = app.dataframe[0].value
    assert agent_table["agent_id"].tolist() == ["A3001"]
