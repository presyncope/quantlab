from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from quantlab.copy import PROHIBITED_TERMS, assert_safe_copy
from quantlab.domain import Grade, generated_alert_eligibility
from quantlab.sample_data import DEMO_DATE, seed_demo
from quantlab.storage import Repository
from quantlab.workflow import create_generated_signal, create_manual_note, markdown_report, summarize_day


def repo(tmp_path: Path) -> Repository:
    r = Repository(tmp_path / "phase1.sqlite3")
    r.reset()
    return r


def test_seed_demo_contains_complete_daily_loop(tmp_path: Path) -> None:
    r = repo(tmp_path)
    assert seed_demo(r) == DEMO_DATE
    day = r.full_day(DEMO_DATE)
    assert day["brief"]
    assert len(day["sectors"]) >= 3
    assert len(day["watchlist"]) >= 4
    assert len(day["cards"]) >= 3
    assert len(day["signals"]) == 2
    assert len(day["decisions"]) == 3
    assert len(day["reviews"]) == 3


def test_watchlist_trade_date_ticker_unique(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    item = r.get_watchlist_item(DEMO_DATE, "000660")
    assert item is not None
    before = item["id"]
    after = r.upsert(
        "premarket_watchlist",
        {
            "trade_date": DEMO_DATE,
            "ticker": "000660",
            "name": "SK하이닉스",
            "market": "KOSPI",
            "sector_tags": "반도체",
            "grade": "A",
            "bias": "upward",
            "score": 91,
            "thesis": "updated",
            "risk_tags": "",
            "observation_price": "VWAP",
            "alert_enabled": 1,
            "final_action": "",
        },
        "trade_date, ticker",
    )
    assert after == before
    updated = r.get_watchlist_item(DEMO_DATE, "000660")
    assert updated is not None
    assert updated["score"] == 91


def test_generated_alert_eligibility_rules(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    a_item = r.get_watchlist_item(DEMO_DATE, "000660")
    c_item = r.get_watchlist_item(DEMO_DATE, "267260")
    excluded = r.get_watchlist_item(DEMO_DATE, "123456")
    assert a_item and c_item and excluded
    signal_id = create_generated_signal(r, a_item["id"], "13:00", "volume_expansion")
    assert signal_id > 0
    with pytest.raises(ValueError, match="A/B candidates"):
        create_generated_signal(r, c_item["id"], "13:01", "volume_expansion")
    with pytest.raises(ValueError, match="A/B candidates"):
        create_generated_signal(r, excluded["id"], "13:02", "volume_expansion")
    note_id = create_manual_note(r, c_item["id"], "13:05", "C등급이라 수동 관찰 메모만 남김")
    assert note_id > 0


def test_domain_eligibility_explains_manual_notes() -> None:
    assert generated_alert_eligibility(Grade.A).eligible
    assert generated_alert_eligibility(Grade.B).eligible
    c = generated_alert_eligibility(Grade.C)
    assert not c.eligible
    assert "manual non-alert note" in c.reason


def test_signal_decision_execution_review_are_separate_tables(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    with r.connect() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "intraday_signal_log",
            "user_decision_log",
            "trade_execution_log",
            "postmarket_review",
        }.issubset(tables)
        signal_id_notnull = [row for row in conn.execute("PRAGMA table_info(user_decision_log)") if row[1] == "signal_id"][0][3]
        assert signal_id_notnull == 0
        fk_tables = {row[2] for row in conn.execute("PRAGMA foreign_key_list(user_decision_log)")}
        assert {"intraday_signal_log", "premarket_watchlist"}.issubset(fk_tables)


def test_summary_rollups_match_seeded_expectations(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    summary = summarize_day(r, DEMO_DATE)
    assert summary["grade_counts"] == {"A": 1, "B": 1, "C": 1, "excluded": 1}
    assert summary["bias_counts"]["upward"] == 2
    assert summary["signal_counts"] == {"vwap_recovery": 1, "previous_high_break": 1}
    assert summary["action_counts"] == {"entered": 1, "held": 1, "note_only": 1}
    assert summary["avg_close_return_by_grade"] == {"A": 2.1, "B": -0.2, "C": -0.8}
    assert summary["generated_alert_violations"] == []
    assert "Phase 1 Daily Report" in markdown_report(r, DEMO_DATE)


def test_copy_guardrails_reject_prohibited_terms() -> None:
    for term in PROHIBITED_TERMS:
        with pytest.raises(ValueError):
            assert_safe_copy(f"This UI says {term}")
    assert_safe_copy("Entry review zone and risk re-evaluation prompt")


def test_no_live_broker_or_order_runtime_imports() -> None:
    forbidden_modules = {
        "OpenDartReader",
        "FinanceDataReader",
        "pykrx",
        "kis_auth",
        "kis_devlp",
        "mojito",
    }
    forbidden_calls = {"place_order", "send_order", "buy", "sell", "get_balance", "get_account"}
    for path in Path("quantlab").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif node.module:
                    names = [node.module.split(".")[0]]
                assert not (set(names) & forbidden_modules), f"{path} imports live adapter {names}"
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                assert name not in forbidden_calls, f"{path} calls forbidden live/order function {name}"


def test_app_startup_imports_without_credentials() -> None:
    import quantlab.app as app

    assert app.DEMO_DATE == DEMO_DATE


def test_seed_demo_is_idempotent(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    first = {key: len(value) for key, value in r.full_day(DEMO_DATE).items()}
    seed_demo(r)
    second = {key: len(value) for key, value in r.full_day(DEMO_DATE).items()}
    assert second == first
    assert second["signals"] == 2
    assert second["decisions"] == 3


def test_storage_trigger_blocks_direct_generated_alert_for_c_grade(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    c_item = r.get_watchlist_item(DEMO_DATE, "267260")
    assert c_item is not None
    with pytest.raises(sqlite3.IntegrityError, match="generated alerts"):
        r.insert(
            "intraday_signal_log",
            {
                "watchlist_item_id": c_item["id"],
                "trade_date": DEMO_DATE,
                "ticker": c_item["ticker"],
                "signal_time": "14:00",
                "signal_type": "volume_expansion",
                "signal_source": "generated_alert",
                "price": 100.0,
                "volume_context": "direct bypass attempt",
                "interpretation": "Review prompt",
            },
        )


def test_research_card_edit_persists(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    item = r.get_watchlist_item(DEMO_DATE, "000660")
    assert item is not None
    r.upsert(
        "stock_research_card",
        {
            "watchlist_item_id": item["id"],
            "trade_date": DEMO_DATE,
            "ticker": item["ticker"],
            "confidence": 5,
            "market_evidence": "updated market",
            "sector_evidence": "updated sector",
            "news_evidence": "updated news",
            "supply_evidence": "updated supply",
            "chart_evidence": "updated chart",
            "risks": "updated risks",
            "price_structure": "updated price structure",
            "scenario": "updated entry review scenario",
            "invalidation": "updated invalidation",
            "stop_criteria": "updated stop criteria",
            "forbidden_conditions": "updated forbidden condition",
            "result_note": "updated result",
        },
        "watchlist_item_id",
    )
    reloaded = r.list_rows("stock_research_card", "watchlist_item_id=?", [item["id"]])[0]
    assert reloaded["confidence"] == 5
    assert reloaded["scenario"] == "updated entry review scenario"
    assert reloaded["invalidation"] == "updated invalidation"
    assert reloaded["stop_criteria"] == "updated stop criteria"


def test_managed_db_path_restricts_streamlit_reset_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quantlab.storage import managed_db_path

    monkeypatch.chdir(tmp_path)
    assert managed_db_path(".quantlab/demo.sqlite3") == Path(".quantlab/demo.sqlite3")
    with pytest.raises(ValueError):
        managed_db_path(str(tmp_path / "outside.sqlite3"))
    with pytest.raises(ValueError):
        managed_db_path("../outside.sqlite3")
    with pytest.raises(ValueError):
        managed_db_path(".quantlab/not-a-db.txt")


def test_repository_reset_refuses_non_sqlite_file(tmp_path: Path) -> None:
    target = tmp_path / "important.sqlite3"
    target.write_text("not sqlite")
    with pytest.raises(ValueError, match="non-SQLite"):
        Repository(target).reset()
    assert target.read_text() == "not sqlite"


def test_sql_helpers_reject_unapproved_fragments(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    with pytest.raises(ValueError):
        r.list_rows("premarket_watchlist; DROP TABLE instrument_master")
    with pytest.raises(ValueError):
        r.list_rows("premarket_watchlist", "1=1; DROP TABLE instrument_master")
    with pytest.raises(ValueError):
        r.list_rows("premarket_watchlist", order_by="score; DROP TABLE instrument_master")


def test_managed_db_path_rejects_dangling_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quantlab.storage import managed_db_path

    monkeypatch.chdir(tmp_path)
    Path(".quantlab").mkdir()
    outside = tmp_path / "outside.sqlite3"
    link = Path(".quantlab/demo.sqlite3")
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        managed_db_path(link)
    with pytest.raises(ValueError, match="symlink"):
        Repository(link).reset()
    assert not outside.exists()


def test_watchlist_cannot_downgrade_while_generated_alerts_exist(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    item = r.get_watchlist_item(DEMO_DATE, "000660")
    assert item is not None
    with pytest.raises(sqlite3.IntegrityError, match="cannot downgrade"):
        r.upsert(
            "premarket_watchlist",
            {
                "trade_date": DEMO_DATE,
                "ticker": "000660",
                "name": "SK하이닉스",
                "market": "KOSPI",
                "sector_tags": "반도체",
                "grade": "C",
                "bias": "watch",
                "score": 50,
                "thesis": "downgrade attempt",
                "risk_tags": "",
                "observation_price": "",
                "alert_enabled": 0,
                "final_action": "",
            },
            "trade_date, ticker",
        )
    unchanged = r.get_watchlist_item(DEMO_DATE, "000660")
    assert unchanged is not None
    assert unchanged["grade"] == "A"
    assert summarize_day(r, DEMO_DATE)["generated_alert_violations"] == []


def test_managed_db_path_rejects_symlinked_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quantlab.storage import managed_db_path

    monkeypatch.chdir(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_db = outside_dir / "victim.sqlite3"
    # Create a valid SQLite file to prove reset must not unlink it through the parent symlink.
    Repository(outside_db).initialize()
    Path(".quantlab").symlink_to(outside_dir, target_is_directory=True)
    with pytest.raises(ValueError, match="directory"):
        managed_db_path(".quantlab/victim.sqlite3")
    with pytest.raises(ValueError, match="directory"):
        Repository(Path(".quantlab/victim.sqlite3")).reset()
    assert outside_db.exists()


def test_repository_initialize_refuses_symlinked_managed_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_db = outside_dir / "phase1.sqlite3"
    Path(".quantlab").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked directory"):
        Repository(Path(".quantlab/phase1.sqlite3")).initialize()

    assert not outside_db.exists()


def test_summary_skips_blank_close_return(tmp_path: Path) -> None:
    r = repo(tmp_path)
    seed_demo(r)
    item = r.get_watchlist_item(DEMO_DATE, "000660")
    assert item is not None
    r.upsert(
        "postmarket_review",
        {
            "watchlist_item_id": item["id"],
            "trade_date": DEMO_DATE,
            "ticker": item["ticker"],
            "grade": "A",
            "bias": "upward",
            "day_high_return": "   ",
            "day_low_return": "   ",
            "close_return": "   ",
            "bias_result": "ambiguous",
            "signal_quality": "normal",
            "execution_quality": "normal",
            "failure_reason": "none",
            "improvement_note": "blank numeric fields from UI",
        },
        "watchlist_item_id",
    )
    summary = summarize_day(r, DEMO_DATE)
    assert summary["avg_close_return_by_grade"] == {"B": -0.2, "C": -0.8}
