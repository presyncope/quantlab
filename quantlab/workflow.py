"""Workflow services and summaries for the Phase 1 local MVP."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from quantlab.copy import assert_safe_copy, safe_label
from quantlab.domain import SignalSource, SignalType, generated_alert_eligibility
from quantlab.storage import Repository


def create_generated_signal(
    repo: Repository,
    watchlist_item_id: int,
    signal_time: str,
    signal_type: str | SignalType,
    price: float | None = None,
    volume_context: str = "",
    interpretation: str = "",
) -> int:
    item = repo.get_watchlist_item_by_id(watchlist_item_id)
    if not item:
        raise ValueError(f"Unknown watchlist item id: {watchlist_item_id}")
    eligibility = generated_alert_eligibility(item["grade"], bool(item["alert_enabled"]))
    if not eligibility.eligible:
        raise ValueError(eligibility.reason)
    signal_value = str(signal_type.value if isinstance(signal_type, SignalType) else signal_type)
    label = safe_label(signal_value)
    text = interpretation or label
    assert_safe_copy(text)
    return repo.insert(
        "intraday_signal_log",
        {
            "watchlist_item_id": watchlist_item_id,
            "trade_date": item["trade_date"],
            "ticker": item["ticker"],
            "signal_time": signal_time,
            "signal_type": signal_value,
            "signal_source": SignalSource.GENERATED_ALERT.value,
            "price": price,
            "volume_context": volume_context,
            "interpretation": text,
        },
    )


def create_manual_note(
    repo: Repository,
    watchlist_item_id: int,
    decision_time: str,
    note: str,
    action: str = "note_only",
) -> int:
    item = repo.get_watchlist_item_by_id(watchlist_item_id)
    if not item:
        raise ValueError(f"Unknown watchlist item id: {watchlist_item_id}")
    assert_safe_copy(note)
    return repo.insert(
        "user_decision_log",
        {
            "signal_id": None,
            "watchlist_item_id": watchlist_item_id,
            "trade_date": item["trade_date"],
            "ticker": item["ticker"],
            "decision_time": decision_time,
            "action": action,
            "note": note,
            "execution_quality": "normal",
        },
    )


def record_decision_for_signal(
    repo: Repository,
    signal_id: int,
    action: str,
    decision_time: str,
    note: str = "",
    execution_quality: str = "normal",
) -> int:
    rows = repo.list_rows("intraday_signal_log", "id=?", [signal_id])
    if not rows:
        raise ValueError(f"Unknown signal id: {signal_id}")
    signal = rows[0]
    assert_safe_copy(note)
    return repo.insert(
        "user_decision_log",
        {
            "signal_id": signal_id,
            "watchlist_item_id": signal["watchlist_item_id"],
            "trade_date": signal["trade_date"],
            "ticker": signal["ticker"],
            "decision_time": decision_time,
            "action": action,
            "note": note,
            "execution_quality": execution_quality,
        },
    )


def operation_sheet(repo: Repository, trade_date: str) -> dict[str, Any]:
    day = repo.full_day(trade_date)
    watchlist = day["watchlist"]
    by_grade: dict[str, list[str]] = defaultdict(list)
    for item in watchlist:
        by_grade[item["grade"]].append(f"{item['name']}({item['ticker']})")
    brief = day["brief"][0] if day["brief"] else {}
    return {
        "trade_date": trade_date,
        "market_mode": brief.get("market_mode", ""),
        "priority_sectors": brief.get("priority_sectors", ""),
        "avoid_sectors": brief.get("avoid_sectors", ""),
        "operating_principles": brief.get("operating_principles", ""),
        "a_grade": by_grade.get("A", []),
        "b_grade": by_grade.get("B", []),
        "c_grade": by_grade.get("C", []),
        "excluded": by_grade.get("excluded", []),
    }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return float(value)


def summarize_day(repo: Repository, trade_date: str) -> dict[str, Any]:
    day = repo.full_day(trade_date)
    watch_by_id = {item["id"]: item for item in day["watchlist"]}
    grade_counts = Counter(item["grade"] for item in day["watchlist"])
    bias_counts = Counter(item["bias"] for item in day["watchlist"])
    signal_counts = Counter(signal["signal_type"] for signal in day["signals"])
    action_counts = Counter(decision["action"] for decision in day["decisions"])
    review_quality = Counter(review["signal_quality"] for review in day["reviews"])
    execution_quality = Counter(review["execution_quality"] for review in day["reviews"])
    failure_reasons = Counter(review["failure_reason"] for review in day["reviews"])
    grade_performance: dict[str, list[float]] = defaultdict(list)
    for review in day["reviews"]:
        close_return = _optional_float(review["close_return"])
        if close_return is not None:
            grade_performance[review["grade"]].append(close_return)
    avg_close_by_grade = {
        grade: round(sum(values) / len(values), 4) for grade, values in grade_performance.items()
    }
    generated_alert_violations = [
        signal
        for signal in day["signals"]
        if watch_by_id.get(signal["watchlist_item_id"], {}).get("grade") not in {"A", "B"}
        and signal["signal_source"] == SignalSource.GENERATED_ALERT.value
    ]
    return {
        "trade_date": trade_date,
        "grade_counts": dict(grade_counts),
        "bias_counts": dict(bias_counts),
        "signal_counts": dict(signal_counts),
        "action_counts": dict(action_counts),
        "signal_quality_counts": dict(review_quality),
        "execution_quality_counts": dict(execution_quality),
        "failure_reason_counts": dict(failure_reasons),
        "avg_close_return_by_grade": avg_close_by_grade,
        "generated_alert_violations": generated_alert_violations,
    }


def markdown_report(repo: Repository, trade_date: str) -> str:
    sheet = operation_sheet(repo, trade_date)
    summary = summarize_day(repo, trade_date)
    lines = [
        f"# {trade_date} Phase 1 Daily Report",
        "",
        f"- Market mode: {sheet['market_mode']}",
        f"- Priority sectors: {sheet['priority_sectors']}",
        f"- Avoid sectors: {sheet['avoid_sectors']}",
        f"- Operating principles: {sheet['operating_principles']}",
        "",
        "## Watchlist",
        f"- A: {', '.join(sheet['a_grade'])}",
        f"- B: {', '.join(sheet['b_grade'])}",
        f"- C: {', '.join(sheet['c_grade'])}",
        f"- Excluded: {', '.join(sheet['excluded'])}",
        "",
        "## Summary",
        f"- Grade counts: {summary['grade_counts']}",
        f"- Bias counts: {summary['bias_counts']}",
        f"- Signal counts: {summary['signal_counts']}",
        f"- Action counts: {summary['action_counts']}",
        f"- Failure reasons: {summary['failure_reason_counts']}",
    ]
    report = "\n".join(lines)
    assert_safe_copy(report)
    return report
