"""Safe UI copy for a research-aid application, not a recommendation engine."""

from __future__ import annotations

PROHIBITED_TERMS = [
    "buy signal",
    "sell signal",
    "strong buy",
    "ai recommendation",
    "target price",
    "buy now",
    "sell now",
    "매수 신호",
    "매도 신호",
    "강력 매수",
    "손절 신호",
    "ai 매수/매도 추천",
    "AI 매수/매도 추천",
]

SAFE_SIGNAL_LABELS = {
    "vwap_recovery": "Entry review zone: VWAP recovery",
    "vwap_loss": "Scenario validity check: VWAP loss",
    "previous_high_break": "Entry review zone: previous high break",
    "intraday_high_break": "Momentum review: intraday high break",
    "volume_expansion": "Participation review: volume expansion",
    "invalidation_approach": "Risk re-evaluation: invalidation level nearby",
    "manual_note": "Manual non-alert review note",
}

APP_INTRO = (
    "Quantlab Phase 1 is a local research and review aid. "
    "Signals are prompts for human review, not trading instructions."
)


def assert_safe_copy(text: str) -> None:
    lowered = text.lower()
    for term in PROHIBITED_TERMS:
        if term.lower() in lowered:
            raise ValueError(f"Prohibited recommendation phrasing found: {term}")


def safe_label(signal_type: str) -> str:
    label = SAFE_SIGNAL_LABELS.get(signal_type, "Review prompt")
    assert_safe_copy(label)
    return label
