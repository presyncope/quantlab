"""Domain vocabulary for the Phase 1 local research loop.

The values here intentionally describe research/review states, not trade advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Market(StrEnum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    WATCH = "watch"
    HALTED = "halted"


class MarketMode(StrEnum):
    RISK_ON = "risk-on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk-off"


class SectorJudgment(StrEnum):
    INTEREST = "interest"
    NEUTRAL = "neutral"
    AVOID = "avoid"


class Grade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    EXCLUDED = "excluded"


ALERT_GRADES = {Grade.A, Grade.B}


class Bias(StrEnum):
    UPWARD = "upward"
    DOWNWARD = "downward"
    NEUTRAL = "neutral"
    WATCH = "watch"


class SignalType(StrEnum):
    VWAP_RECOVERY = "vwap_recovery"
    VWAP_LOSS = "vwap_loss"
    PREV_HIGH_BREAK = "previous_high_break"
    INTRADAY_HIGH_BREAK = "intraday_high_break"
    VOLUME_EXPANSION = "volume_expansion"
    INVALIDATION_APPROACH = "invalidation_approach"
    MANUAL_NOTE = "manual_note"


class SignalSource(StrEnum):
    GENERATED_ALERT = "generated_alert"
    MANUAL_NOTE = "manual_note"


class UserAction(StrEnum):
    ENTERED = "entered"
    HELD = "held"
    IGNORED = "ignored"
    MISSED = "missed"
    REMOVED = "removed"
    NOTE_ONLY = "note_only"


class Quality(StrEnum):
    GOOD = "good"
    NORMAL = "normal"
    BAD = "bad"
    TOO_EARLY = "too_early"
    TOO_LATE = "too_late"
    IMPULSIVE = "impulsive"
    AMBIGUOUS = "ambiguous"


class BiasResult(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    AMBIGUOUS = "ambiguous"


class FailureReason(StrEnum):
    RESEARCH = "research"
    SIGNAL = "signal"
    EXECUTION = "execution"
    RISK = "risk"
    MARKET_SHIFT = "market_shift"
    NONE = "none"


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reason: str


def normalize_grade(value: str | Grade) -> Grade:
    if isinstance(value, Grade):
        return value
    lowered = value.lower()
    if lowered in {"excluded", "exclude", "제외"}:
        return Grade.EXCLUDED
    return Grade(value.upper())


def generated_alert_eligibility(grade: str | Grade, alert_enabled: bool = True) -> EligibilityResult:
    """Return whether a watchlist item may receive generated alert records.

    Phase 1 allows generated alerts for A/B candidates only. C/Excluded items may still
    receive manual review notes, but those notes are not generated alerts.
    """

    normalized = normalize_grade(grade)
    if normalized not in ALERT_GRADES:
        return EligibilityResult(
            False,
            "Generated alerts are limited to A/B candidates; use a manual non-alert note instead.",
        )
    if not alert_enabled:
        return EligibilityResult(False, "Alert flag is disabled for this watchlist item.")
    return EligibilityResult(True, "Generated alert is allowed for this A/B candidate.")
