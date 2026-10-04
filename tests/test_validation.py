from __future__ import annotations

from src.data_loader import load_data
from src.preprocessing import prepare_tickets
from src.validation import validate_data


def test_supplied_data_has_unique_tickets_valid_agent_and_product_joins() -> None:
    bundle = load_data()
    prepared = prepare_tickets(bundle.tickets)
    report = validate_data(bundle.tickets, bundle.agents, bundle.products, bundle.orders, prepared).to_frame().set_index("check")
    assert report.loc["Duplicate ticket IDs", "count"] == 0
    assert report.loc["Missing agent IDs", "count"] == 0
    assert report.loc["Unknown agent IDs", "count"] == 0
    assert report.loc["Invalid CSAT values", "count"] == 0
    assert report.loc["Unknown product SKU", "count"] == 0
    assert report.loc["Unknown nonblank order IDs", "count"] == 0
    assert report.loc["Negative normalized AHT", "count"] == 0


def test_duplicate_names_are_reported_without_using_them_as_join_keys() -> None:
    bundle = load_data()
    report = validate_data(bundle.tickets, bundle.agents, bundle.products, bundle.orders).to_frame().set_index("check")
    assert report.loc["Duplicate display-name roster rows", "count"] == 2
    assert report.loc["Duplicate display-name roster rows", "status"] == "Report"

