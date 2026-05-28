"""Streamlit local dashboard for Quantlab Phase 1."""

from __future__ import annotations

from typing import Any, cast

from quantlab.copy import APP_INTRO, assert_safe_copy, safe_label
from quantlab.domain import Bias, Grade, MarketMode, SectorJudgment, SignalType, UserAction
from quantlab.sample_data import DEMO_DATE, seed_demo
from quantlab.storage import DEFAULT_DB_PATH, Repository, managed_db_path
from quantlab.workflow import create_generated_signal, create_manual_note, markdown_report, operation_sheet, record_decision_for_signal, summarize_day

try:  # pragma: no cover - UI import smoke-tested separately when dependency exists.
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Streamlit dashboard dependencies are not installed. Install with `pip install -e .` "
        "or use the tested domain/storage workflow modules directly."
    ) from exc


def repo() -> Repository:
    raw_path = st.sidebar.text_input("SQLite DB path", str(DEFAULT_DB_PATH))
    try:
        path = managed_db_path(raw_path)
    except ValueError as exc:
        st.sidebar.error(str(exc))
        st.stop()
    return Repository(path)


def as_text(value: Any) -> str:
    return "" if value is None else str(value)


def table(rows: list[dict[str, Any]]) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No records yet.")


def editable_dataframe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=key)
    return edited.fillna("").to_dict("records")


def save_market_brief(r: Repository, trade_date: str) -> None:
    existing = r.list_rows("daily_market_brief", "trade_date=?", [trade_date])
    row = existing[0] if existing else {}
    with st.form("market_brief"):
        market_mode = st.selectbox("Market mode", [m.value for m in MarketMode], index=[m.value for m in MarketMode].index(row.get("market_mode", MarketMode.NEUTRAL.value)) if row.get("market_mode") in [m.value for m in MarketMode] else 1)
        kospi_note = st.text_area("KOSPI note", row.get("kospi_note", ""))
        kosdaq_note = st.text_area("KOSDAQ note", row.get("kosdaq_note", ""))
        overseas_impact = st.text_area("Overseas impact", row.get("overseas_impact", ""))
        fx_rates_note = st.text_area("FX/rates", row.get("fx_rates_note", ""))
        major_events = st.text_area("Major events", row.get("major_events", ""))
        priority_sectors = st.text_input("Priority sectors", row.get("priority_sectors", ""))
        avoid_sectors = st.text_input("Avoid sectors", row.get("avoid_sectors", ""))
        operating_principles = st.text_area("Operating principles", row.get("operating_principles", ""))
        if st.form_submit_button("Save market brief"):
            assert_safe_copy(" ".join(as_text(value) for value in [kospi_note, kosdaq_note, overseas_impact, operating_principles]))
            r.upsert(
                "daily_market_brief",
                {
                    "trade_date": trade_date,
                    "market_mode": market_mode,
                    "kospi_note": kospi_note,
                    "kosdaq_note": kosdaq_note,
                    "overseas_impact": overseas_impact,
                    "fx_rates_note": fx_rates_note,
                    "major_events": major_events,
                    "priority_sectors": priority_sectors,
                    "avoid_sectors": avoid_sectors,
                    "operating_principles": operating_principles,
                },
                "trade_date",
            )
            st.success("Saved market brief")


def normalize_optional_number(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return None if not stripped else stripped
    return None if value == "" else value


def save_rows(r: Repository, table_name: str, rows: list[dict[str, Any]], conflict: str) -> None:
    for row in rows:
        clean = {k: v for k, v in row.items() if k != "id" and str(v) != "nan"}
        if clean:
            r.upsert(table_name, clean, conflict)


def main() -> None:
    st.set_page_config(page_title="Quantlab Phase 1", layout="wide")
    st.title("Quantlab Phase 1 Local MVP")
    st.caption(APP_INTRO)
    r = repo()
    r.initialize()

    if st.sidebar.button("Reset and seed demo data"):
        r.reset()
        seed_demo(r)
        st.sidebar.success(f"Seeded {DEMO_DATE}")

    dates = sorted({row["trade_date"] for row in r.list_rows("premarket_watchlist")}) or [DEMO_DATE]
    trade_date = cast(str, st.sidebar.selectbox("Trade date", dates))

    tabs = st.tabs([
        "Setup/Demo",
        "Market Brief",
        "Sector Map",
        "Watchlist & Cards",
        "Signals & Actions",
        "Postmarket Review",
        "Summary",
    ])

    with tabs[0]:
        st.subheader("Local/offline setup")
        st.write("This app stores local SQLite records only. It does not connect to broker APIs, accounts, or order systems.")
        st.code(f"Current DB: {r.path}")
        if st.button("Seed demo date", key="seed-main"):
            seed_demo(r)
            st.success(f"Seeded {DEMO_DATE}")
        st.write("Full day state")
        st.json(r.full_day(trade_date))

    with tabs[1]:
        st.subheader("Market brief")
        save_market_brief(r, trade_date)

    with tabs[2]:
        st.subheader("Sector/theme map")
        rows = r.list_rows("sector_theme_map", "trade_date=?", [trade_date], "sector_name") or [
            {"trade_date": trade_date, "sector_name": "", "prior_move": "", "volume_change": "", "leader": "", "laggards": "", "news_note": "", "overseas_linkage": "", "overheated": 0, "judgment": SectorJudgment.NEUTRAL.value}
        ]
        edited = editable_dataframe(rows, "sectors")
        if st.button("Save sector map"):
            save_rows(r, "sector_theme_map", edited, "trade_date, sector_name")
            st.success("Saved sectors")

    with tabs[3]:
        st.subheader("Watchlist")
        wl = r.list_rows("premarket_watchlist", "trade_date=?", [trade_date], "grade, score DESC")
        table(wl)
        with st.form("add_watch"):
            ticker = st.text_input("Ticker")
            name = st.text_input("Name")
            market = st.text_input("Market", "KOSPI")
            sector_tags = st.text_input("Sector tags")
            grade = st.selectbox("Grade", [g.value for g in Grade])
            bias = st.selectbox("Bias", [b.value for b in Bias])
            score = st.number_input("Score", 0, 100, 50)
            thesis = st.text_area("Thesis")
            risk_tags = st.text_input("Risk tags")
            observation_price = st.text_input("Observation price")
            alert_enabled = st.checkbox("Alert enabled", value=grade in {Grade.A.value, Grade.B.value})
            if st.form_submit_button("Save watchlist item") and ticker:
                assert_safe_copy(thesis)
                r.upsert("instrument_master", {"ticker": ticker, "name": name, "market": market, "sector_tags": sector_tags, "listing_status": "active"}, "ticker")
                item_id = r.upsert("premarket_watchlist", {"trade_date": trade_date, "ticker": ticker, "name": name, "market": market, "sector_tags": sector_tags, "grade": grade, "bias": bias, "score": int(score), "thesis": thesis, "risk_tags": risk_tags, "observation_price": observation_price, "alert_enabled": int(alert_enabled), "final_action": ""}, "trade_date, ticker")
                r.upsert("stock_research_card", {"watchlist_item_id": item_id, "trade_date": trade_date, "ticker": ticker}, "watchlist_item_id")
                st.success("Saved watchlist item")
        st.subheader("Research cards")
        cards = r.list_rows("stock_research_card", "trade_date=?", [trade_date], "ticker")
        if cards:
            card_options = {f"{card['ticker']} card #{card['id']}": card for card in cards}
            selected_card = card_options[st.selectbox("Research card", list(card_options))]
            with st.form("research_card_editor"):
                confidence = st.number_input("Confidence", 1, 5, int(selected_card.get("confidence") or 3))
                market_evidence = st.text_area("Market evidence", selected_card.get("market_evidence", ""))
                sector_evidence = st.text_area("Sector evidence", selected_card.get("sector_evidence", ""))
                news_evidence = st.text_area("News/disclosure evidence", selected_card.get("news_evidence", ""))
                supply_evidence = st.text_area("Supply/demand evidence", selected_card.get("supply_evidence", ""))
                chart_evidence = st.text_area("Chart evidence", selected_card.get("chart_evidence", ""))
                risks = st.text_area("Risks", selected_card.get("risks", ""))
                price_structure = st.text_area("Price structure", selected_card.get("price_structure", ""))
                scenario = st.text_area("Entry review scenario", selected_card.get("scenario", ""))
                invalidation = st.text_area("Invalidation", selected_card.get("invalidation", ""))
                stop_criteria = st.text_area("Stop criteria", selected_card.get("stop_criteria", ""))
                forbidden_conditions = st.text_area("Forbidden conditions", selected_card.get("forbidden_conditions", ""))
                result_note = st.text_area("Result note", selected_card.get("result_note", ""))
                if st.form_submit_button("Save research card"):
                    text_blob = " ".join(as_text(value) for value in [market_evidence, sector_evidence, news_evidence, supply_evidence, chart_evidence, risks, price_structure, scenario, invalidation, stop_criteria, forbidden_conditions, result_note])
                    assert_safe_copy(text_blob)
                    r.upsert(
                        "stock_research_card",
                        {
                            "watchlist_item_id": selected_card["watchlist_item_id"],
                            "trade_date": selected_card["trade_date"],
                            "ticker": selected_card["ticker"],
                            "confidence": int(confidence),
                            "market_evidence": market_evidence,
                            "sector_evidence": sector_evidence,
                            "news_evidence": news_evidence,
                            "supply_evidence": supply_evidence,
                            "chart_evidence": chart_evidence,
                            "risks": risks,
                            "price_structure": price_structure,
                            "scenario": scenario,
                            "invalidation": invalidation,
                            "stop_criteria": stop_criteria,
                            "forbidden_conditions": forbidden_conditions,
                            "result_note": result_note,
                        },
                        "watchlist_item_id",
                    )
                    st.success("Saved research card")
        table(cards)

    with tabs[4]:
        st.subheader("Signals and actions")
        st.write("Generated alerts are limited to A/B candidates. C/Excluded rows may receive manual non-alert review notes only.")
        wl = r.list_rows("premarket_watchlist", "trade_date=?", [trade_date], "grade, score DESC")
        options = {f"{row['grade']} {row['name']}({row['ticker']}) #{row['id']}": row for row in wl}
        if options:
            selected = options[st.selectbox("Watchlist item", list(options))]
            mode = st.radio("Record type", ["Generated alert", "Manual non-alert note"])
            if mode == "Generated alert":
                st.info(safe_label(SignalType.VWAP_RECOVERY.value))
                signal_type = st.selectbox("Signal type", [s.value for s in SignalType if s != SignalType.MANUAL_NOTE])
                signal_time = st.text_input("Signal time", "09:30")
                price = st.number_input("Price", min_value=0.0, value=0.0)
                volume_context = st.text_input("Volume context")
                if st.button("Create generated alert"):
                    try:
                        create_generated_signal(r, selected["id"], signal_time, signal_type, price or None, volume_context)
                        st.success("Generated alert recorded")
                    except ValueError as exc:
                        st.error(str(exc))
            else:
                note = st.text_area("Manual review note")
                if st.button("Create manual note"):
                    create_manual_note(r, selected["id"], "", note)
                    st.success("Manual non-alert note recorded")
        st.subheader("Signals")
        table(r.list_rows("intraday_signal_log", "trade_date=?", [trade_date], "signal_time"))
        st.subheader("Decisions")
        signals = r.list_rows("intraday_signal_log", "trade_date=?", [trade_date], "signal_time")
        sig_options = {f"#{row['id']} {row['ticker']} {row['signal_type']}": row for row in signals}
        if sig_options:
            sig = sig_options[st.selectbox("Signal", list(sig_options))]
            action = st.selectbox("Action", [a.value for a in UserAction])
            note = st.text_area("Decision note")
            if st.button("Record decision"):
                record_decision_for_signal(r, sig["id"], action, "", note)
                st.success("Decision recorded")
        table(r.list_rows("user_decision_log", "trade_date=?", [trade_date], "decision_time"))

    with tabs[5]:
        st.subheader("Postmarket review")
        rows = r.list_rows("postmarket_review", "trade_date=?", [trade_date], "ticker")
        edited = editable_dataframe(rows, "reviews")
        if st.button("Save reviews"):
            for row in edited:
                row = {k: v for k, v in row.items() if k != "id"}
                for numeric_field in ["day_high_return", "day_low_return", "close_return"]:
                    if numeric_field in row:
                        row[numeric_field] = normalize_optional_number(row[numeric_field])
                r.upsert("postmarket_review", row, "watchlist_item_id")
            st.success("Saved reviews")

    with tabs[6]:
        st.subheader("Operation sheet")
        st.json(operation_sheet(r, trade_date))
        st.subheader("Summary rollups")
        st.json(summarize_day(r, trade_date))
        st.subheader("Markdown report")
        st.code(markdown_report(r, trade_date), language="markdown")


if __name__ == "__main__":
    main()
