"""Vireo Audio Support Performance & Training Analytics Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai_classifier import AIClassifier, ai_validation_summary
from src.ai_prompts import PROMPT_HISTORY, PROMPT_VERSION, system_prompt
from src.business_impact import calculate_business_impact
from src.config import DEFAULT_AHT_WEIGHT, DEFAULT_CSAT_WEIGHT, DEFAULT_SAMPLE_SIZE
from src.data_loader import load_data
from src.flagging import score_agents, select_recognition_candidates, select_training_candidates
from src.metrics import agent_metrics, apply_filters, filter_roster, issue_breakdown, monthly_trends, overall_metrics
from src.peer_analysis import derive_minimum_rated_tickets
from src.preprocessing import prepare_tickets, redact_ticket_text
from src.validation import independent_metric_checks, validate_data


st.set_page_config(page_title="Vireo Support Analytics", page_icon="🎧", layout="wide")


@st.cache_data(show_spinner="Loading and validating support data…")
def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bundle = load_data()
    prepared = prepare_tickets(bundle.tickets)
    report = validate_data(bundle.tickets, bundle.agents, bundle.products, bundle.orders, prepared).to_frame()
    return prepared, bundle.agents, bundle.products, bundle.orders, report


def inr(value: float | int) -> str:
    return f"₹{value:,.0f}"


def number(value: float, decimals: int = 2, suffix: str = "") -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}{suffix}"


def display_metric_cards(summary: dict[str, float | int], roster_count: int, candidate_count: int) -> None:
    cards = st.columns(6)
    cards[0].metric("Total tickets", f"{summary['total_tickets']:,}")
    cards[1].metric("Roster agents", f"{roster_count:,}")
    cards[2].metric("Overall CSAT", number(float(summary["csat"]), suffix=" / 5"))
    cards[3].metric("Overall AHT", number(float(summary["aht_minutes"]), 0, " min"))
    cards[4].metric("CSAT response rate", number(float(summary["csat_response_rate"]) * 100, 1, "%"))
    cards[5].metric("Training review candidates", f"{candidate_count} / 10")


def style_agent_table(table: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "agent_id", "name", "site", "team", "shift", "tier", "ticket_volume", "rated_tickets", "csat",
        "aht_minutes", "csat_response_rate", "breach_count", "transfers", "repeat_contacts", "peer_csat",
        "peer_aht_minutes", "csat_peer_gap", "aht_peer_gap_minutes", "review_status", "review_reason",
    ]
    available = [column for column in columns if column in table.columns]
    result = table[available].copy()
    for column in ("csat", "aht_minutes", "csat_response_rate", "peer_csat", "peer_aht_minutes", "csat_peer_gap", "aht_peer_gap_minutes"):
        if column in result:
            result[column] = result[column].round(2)
    if "csat_response_rate" in result:
        result["csat_response_rate"] = (result["csat_response_rate"] * 100).round(1)
    return result.sort_values(["tier", "review_status", "csat"], ascending=[True, True, True], na_position="last")


def sidebar_filters(tickets: pd.DataFrame, agents: pd.DataFrame) -> tuple[pd.DataFrame, int, float, float]:
    st.sidebar.header("Analysis filters")
    date_min = tickets["created_at_dt"].min().date()
    date_max = tickets["created_at_dt"].max().date()
    date_range = st.sidebar.date_input("Ticket-created date", value=(date_min, date_max), min_value=date_min, max_value=date_max)
    if not isinstance(date_range, tuple) or len(date_range) != 2:
        start_date, end_date = date_min, date_max
    else:
        start_date, end_date = date_range

    roster = agents.sort_values("agent_id")
    site = st.sidebar.multiselect("Site", sorted(roster["site"].dropna().unique()))
    team = st.sidebar.multiselect("Team", sorted(roster["team"].dropna().unique()))
    shift = st.sidebar.multiselect("Shift", sorted(roster["shift"].dropna().unique()))
    tier = st.sidebar.multiselect("Tier", sorted(roster["tier"].dropna().unique()))
    selected_agents = st.sidebar.multiselect(
        "Agent", roster["agent_id"].tolist(), format_func=lambda agent_id: f"{agent_id} — {roster.loc[roster['agent_id'].eq(agent_id), 'name'].iloc[0]}"
    )
    filtered = apply_filters(tickets, agents, start_date, end_date, site, team, shift, tier, selected_agents)
    active_roster = filter_roster(agents, site, team, shift, tier, selected_agents)
    # Agent selection narrows what is displayed. Its peer baseline remains the
    # selected date/site/team/shift/tier context, without an agent-ID filter.
    peer_tickets = apply_filters(tickets, agents, start_date, end_date, site, team, shift, tier)
    peer_roster = filter_roster(agents, site, team, shift, tier)
    raw_metrics = agent_metrics(peer_tickets, peer_roster)
    recommended_minimum = derive_minimum_rated_tickets(raw_metrics)
    upper = max(1, int(raw_metrics["rated_tickets"].max()))
    if upper == 1:
        # Streamlit rejects a slider when min_value == max_value. A cohort with
        # no more than one rating per agent has only one usable threshold, so
        # make that constraint explicit instead of rendering an invalid control.
        minimum_rated = 1
        st.sidebar.caption("Minimum rated tickets: 1 (fixed because this filtered cohort has at most one rating per agent)")
    else:
        minimum_rated = st.sidebar.slider(
            "Minimum rated tickets", min_value=1, max_value=upper, value=min(recommended_minimum, upper),
            help="Default is the first quartile of positive Tier 1 rated-ticket counts in the current filter, so it is data-derived and configurable.",
        )
    st.sidebar.caption(f"Data-derived default: {recommended_minimum} rated tickets")
    st.sidebar.subheader("Review-score weights")
    csat_weight = st.sidebar.slider("CSAT weight", 0.0, 1.0, DEFAULT_CSAT_WEIGHT, 0.05)
    aht_weight = st.sidebar.slider("AHT weight", 0.0, 1.0, DEFAULT_AHT_WEIGHT, 0.05)
    if csat_weight + aht_weight == 0:
        st.sidebar.warning("At least one score weight must be above zero; CSAT weighting will be used.")
        csat_weight = 1.0
    return filtered, active_roster, peer_tickets, peer_roster, minimum_rated, csat_weight, aht_weight


def executive_page(
    tickets: pd.DataFrame,
    products: pd.DataFrame,
    scored: pd.DataFrame,
    candidates: pd.DataFrame,
    roster_count: int,
) -> None:
    st.header("Executive overview")
    st.caption("Ticket-created period selected in the sidebar. CSAT uses respondents only; AHT is first response to normalized resolution.")
    summary = overall_metrics(tickets)
    display_metric_cards(summary, roster_count, len(candidates))
    trends = monthly_trends(tickets)
    first, second = st.columns(2)
    with first:
        st.plotly_chart(
            px.line(trends, x="month", y="csat", markers=True, title="Monthly CSAT (rated tickets only)", labels={"month": "Month", "csat": "CSAT / 5"}),
            use_container_width=True,
        )
    with second:
        st.plotly_chart(
            px.line(trends, x="month", y="aht_minutes", markers=True, title="Monthly AHT", labels={"month": "Month", "aht_minutes": "Minutes"}),
            use_container_width=True,
        )
    first, second = st.columns(2)
    with first:
        st.plotly_chart(
            px.bar(trends, x="month", y="ticket_volume", title="Monthly ticket volume", labels={"month": "Month", "ticket_volume": "Tickets"}),
            use_container_width=True,
        )
    with second:
        st.plotly_chart(
            px.line(trends, x="month", y="breach_rate", markers=True, title="First-response breach rate", labels={"month": "Month", "breach_rate": "Rate"}).update_yaxes(tickformat=".0%"),
            use_container_width=True,
        )

    st.subheader("Decision context")
    st.warning("Training review flags are coaching-review evidence, not an employee-quality judgment. Tier 2 is not ranked with Tier 1, and hardware/warranty queue mix can affect CSAT.")
    st.info("Q3 training budget: ₹4,00,000. Use this dashboard to prioritise evidence-backed reviews; it does not allocate or forecast the budget.")
    if candidates.empty:
        st.info("No Tier 1 agents meet the current evidence threshold.")
    else:
        names = ", ".join(candidates["agent_id"].tolist())
        st.write(f"{len(candidates)} evidence-backed Tier 1 training-review candidates under the active configuration: {names}.")

    impact = calculate_business_impact(tickets, products)
    st.subheader("Policy-based business impact")
    st.caption("These are separate planning/cost lines and are deliberately not summed, to avoid double counting.")
    impact_cards = st.columns(4)
    impact_cards[0].metric("Replacement planning cost", inr(impact["replacement_planning_cost_inr"]), f"{impact['replacement_count']:,} issued")
    impact_cards[1].metric("SLA breach credits", inr(impact["breach_credit_cost_inr"]), f"{impact['breach_count']:,} breached tickets")
    impact_cards[2].metric("Contact operating cost", inr(impact["contact_operating_cost_inr"]), "channel-specific policy rates")
    impact_cards[3].metric("Transfer re-handling cost", inr(impact["transfer_rehandling_cost_inr"]), f"{impact['transfer_count']:,} transfers")
    st.caption("Replacement = product unit cost + ₹340 logistics. Breaches = ₹350 credit each. Transfer cost = ₹305 each. Contact cost uses the policy channel rate. None implies a savings opportunity or an attributable agent cost.")


def agent_performance_page(scored: pd.DataFrame) -> None:
    st.header("Agent performance")
    st.caption("Peer baselines are ticket/rating-weighted within the same Tier + team. Tier 2 is descriptive/contextual and excluded from review ranking.")
    st.dataframe(style_agent_table(scored), use_container_width=True, hide_index=True)
    st.subheader("Top 5 recognition candidates")
    st.caption("Separate from review flags: positive peer-normalized CSAT and AHT evidence, subject to the same data threshold and Tier 1 scope.")
    recognition = select_recognition_candidates(scored)
    st.dataframe(
        recognition[["agent_id", "name", "team", "rated_tickets", "csat", "aht_minutes", "csat_peer_gap", "aht_peer_gap_minutes", "recognition_score"]].round(2),
        use_container_width=True,
        hide_index=True,
    )


def csat_aht_page(scored: pd.DataFrame) -> None:
    st.header("CSAT vs AHT")
    st.caption("Bubble size is ticket volume. This is a diagnostic view, not a causal inference; Tier 2 points are labelled contextual.")
    plot_data = scored.loc[scored["ticket_volume"] > 0].copy()
    fig = px.scatter(
        plot_data,
        x="aht_minutes",
        y="csat",
        size="ticket_volume",
        color="review_status",
        symbol="tier",
        hover_name="name",
        hover_data={
            "agent_id": True, "team": True, "tier": True, "ticket_volume": True, "rated_tickets": True,
            "aht_minutes": ":.1f", "csat": ":.2f", "review_score": ":.2f",
        },
        labels={"aht_minutes": "Average AHT (minutes)", "csat": "Average CSAT", "review_status": "Review status"},
        title="Agent CSAT vs average handle time",
        size_max=45,
    )
    st.plotly_chart(fig, use_container_width=True)


def training_page(tickets: pd.DataFrame, candidates: pd.DataFrame) -> None:
    st.header("Training review")
    st.caption("The deterministic score selects up to ten eligible Tier 1 candidates. Text analysis informs aggregate themes; it does not make the review decision.")
    if candidates.empty:
        st.info("No candidates meet the selected minimum evidence threshold.")
        return
    display_columns = ["agent_id", "name", "team", "ticket_volume", "rated_tickets", "csat", "aht_minutes", "csat_peer_gap", "aht_peer_gap_minutes", "review_score", "review_reason"]
    st.dataframe(candidates[display_columns].round(2), use_container_width=True, hide_index=True)
    selected = st.selectbox("Inspect candidate", candidates["agent_id"].tolist(), format_func=lambda item: f"{item} — {candidates.loc[candidates['agent_id'].eq(item), 'name'].iloc[0]}")
    candidate_tickets = tickets.loc[tickets["agent_id"].eq(selected)]
    categories = issue_breakdown(candidate_tickets)
    first, second = st.columns((1, 1))
    with first:
        st.subheader("Observed issue categories")
        st.dataframe(categories[["category", "tickets", "share", "csat"]].assign(share=lambda frame: (frame["share"] * 100).round(1)), use_container_width=True, hide_index=True)
    with second:
        st.subheader("Operational indicators")
        st.metric("Repeat contacts (same category, 30 days)", int(candidate_tickets["is_repeat_contact"].sum()))
        st.metric("Transfers", int(candidate_tickets["transfers"].sum()))
        st.metric("First-response breaches", int(candidate_tickets["is_breached"].sum()))
        st.caption("Repeat-contact flag uses a same-customer, same-category contact within 30 days of a completed ticket. It is contextual, not a quality score.")

    st.subheader("Optional AI-assisted sampled analysis")
    st.caption("Runs at most 20 non-junk tickets for the selected candidate, caches structured JSON in artifacts/ai_cache, and does not call an LLM without LLM_API_KEY. Settings can come from the project .env file or process environment.")
    classifier = AIClassifier()
    if not classifier.available:
        st.info("AI unavailable. Add LLM_API_KEY to .env (or your process environment), then restart Streamlit. LLM_MODEL and LLM_BASE_URL are optional. All deterministic insights remain available.")
    else:
        st.success(f"AI configured: {classifier.provider_label} / {classifier.model}. No ticket text is sent until you select Run / reuse cached AI sample.")
    if st.button("Run / reuse cached AI sample", type="secondary"):
        with st.spinner("Classifying a bounded sample…"):
            taxonomy = sorted(tickets["category"].dropna().unique().tolist())
            results = classifier.classify_sample(candidate_tickets, taxonomy, DEFAULT_SAMPLE_SIZE)
        available_results = results.loc[results["source"].isin(["llm", "cache"])]
        if available_results.empty:
            st.warning(results["error"].iloc[0] if not results.empty else "No eligible text sample was available.")
        else:
            one, two = st.columns(2)
            with one:
                st.write("Issue categories")
                st.dataframe(available_results.groupby("issue_category").size().rename("tickets").sort_values(ascending=False), use_container_width=True)
            with two:
                st.write("Resolution/training themes")
                st.dataframe(available_results.groupby(["resolution_quality_signal", "training_theme"]).size().rename("tickets").sort_values(ascending=False), use_container_width=True)
            st.dataframe(available_results[["ticket_id", "issue_category", "sub_category", "confidence", "resolution_quality_signal", "training_theme", "evidence", "source"]], use_container_width=True, hide_index=True)

    with st.expander("De-identified ticket examples (opt-in)"):
        examples = candidate_tickets[["ticket_id", "category", "customer_message", "agent_notes"]].head(8).copy()
        examples["customer_message"] = examples["customer_message"].map(redact_ticket_text)
        examples["agent_notes"] = examples["agent_notes"].map(redact_ticket_text)
        st.caption("Order IDs, email addresses and 10-digit phone numbers are redacted. Customer data is not used in scoring.")
        st.dataframe(examples, use_container_width=True, hide_index=True)


def validation_page(
    tickets: pd.DataFrame,
    agents: pd.DataFrame,
    products: pd.DataFrame,
    report: pd.DataFrame,
    scored: pd.DataFrame,
) -> None:
    st.header("Data & validation")
    st.caption("Exceptions are reported rather than silently removed. ‘Report’ flags a known caveat; it is not necessarily a data failure.")
    st.dataframe(report, use_container_width=True, hide_index=True)
    st.subheader("Independent deterministic metric spot checks")
    checks = independent_metric_checks(tickets, scored)
    st.dataframe(checks.round(8), use_container_width=True, hide_index=True)
    if not checks.empty and checks["result"].eq("Pass").all():
        st.success("Sampled dashboard metrics match direct ticket-row calculations within 1e-9.")
    st.subheader("AI validation")
    summary = ai_validation_summary(None)
    st.info(summary["message"] + " Use a 50–100 ticket human-labelled set before reporting accuracy or error rate.")
    template = tickets.loc[~tickets["is_junk_ivr"], ["ticket_id", "category"]].head(50).rename(columns={"category": "source_category_reference"})
    template["human_issue_category"] = ""
    template["ai_issue_category"] = ""
    st.download_button("Download AI validation template (50 tickets)", template.to_csv(index=False), "ai_validation_template.csv", "text/csv")
    st.subheader("Prompt versioning")
    st.write(f"Current prompt: **{PROMPT_VERSION}**")
    st.dataframe(pd.DataFrame(PROMPT_HISTORY.items(), columns=["version", "change"]), use_container_width=True, hide_index=True)
    with st.expander("View active AI prompt (v3)"):
        st.code(system_prompt(sorted(tickets["category"].dropna().unique().tolist())), language="text")
    st.subheader("Deliberately out of scope")
    st.markdown(
        "- Full order and customer segmentation analytics\n"
        "- Per-ticket LLM calls across the full dataset\n"
        "- Predictive models, custom ML, and a production API\n"
        "- Automated employee, compensation, or disciplinary decisions\n\n"
        "These were excluded to keep the five-hour MVP focused on an explainable training-review decision."
    )
    st.subheader("Method notes")
    st.markdown(
        "- Legacy `resolved_at` is converted from UTC to IST (+05:30) before AHT.\n"
        "- CSAT excludes blank scores.\n"
        "- Tier 2 is visible but not ranked in Tier 1 review/recognition views.\n"
        "- Source ticket categories provide full-population issue counts; optional AI classifies only a small cached sample."
    )


def main() -> None:
    prepared, agents, products, _orders, report = load_dashboard_data()
    st.title("Vireo Audio Support Performance & Training Analytics")
    st.caption("Decision support for Q3 training review — not an automated employee evaluation.")
    tickets, active_roster, peer_tickets, peer_roster, minimum_rated, csat_weight, aht_weight = sidebar_filters(prepared, agents)
    peer_metrics = agent_metrics(peer_tickets, peer_roster)
    all_scored = score_agents(peer_metrics, minimum_rated, csat_weight, aht_weight)
    scored = all_scored.loc[all_scored["agent_id"].isin(active_roster["agent_id"])].copy()
    all_candidates = select_training_candidates(all_scored)
    candidates = all_candidates.loc[all_candidates["agent_id"].isin(active_roster["agent_id"])].copy()
    candidate_ids = set(candidates["agent_id"])
    scored.loc[scored["agent_id"].isin(candidate_ids), "review_status"] = "Training review candidate"
    page = st.sidebar.radio("Page", ["Executive Overview", "Agent Performance", "CSAT vs AHT", "Training Review", "Data & Validation"])
    if page == "Executive Overview":
        executive_page(tickets, products, scored, candidates, len(agents))
    elif page == "Agent Performance":
        agent_performance_page(scored)
    elif page == "CSAT vs AHT":
        csat_aht_page(scored)
    elif page == "Training Review":
        training_page(tickets, candidates)
    else:
        validation_page(tickets, agents, products, report, scored)


if __name__ == "__main__":
    main()
