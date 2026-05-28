"""Deterministic sample data for the local MVP."""

from __future__ import annotations

from quantlab.domain import Bias, Grade, Market, MarketMode, SectorJudgment, SignalType
from quantlab.storage import Repository
from quantlab.workflow import create_generated_signal, create_manual_note, record_decision_for_signal

DEMO_DATE = "2026-05-28"


def seed_demo(repo: Repository) -> str:
    repo.initialize()
    instruments = [
        {"ticker": "000660", "name": "SK하이닉스", "market": Market.KOSPI.value, "sector_tags": "반도체,HBM", "listing_status": "active"},
        {"ticker": "042700", "name": "한미반도체", "market": Market.KOSPI.value, "sector_tags": "반도체,장비", "listing_status": "active"},
        {"ticker": "267260", "name": "HD현대일렉트릭", "market": Market.KOSPI.value, "sector_tags": "전력기기", "listing_status": "active"},
        {"ticker": "123456", "name": "예시게임", "market": Market.KOSDAQ.value, "sector_tags": "게임", "listing_status": "watch"},
    ]
    for row in instruments:
        repo.upsert("instrument_master", row, "ticker")

    repo.upsert(
        "daily_market_brief",
        {
            "trade_date": DEMO_DATE,
            "market_mode": MarketMode.NEUTRAL.value,
            "kospi_note": "전일 대형주 중심 반등, 거래대금 증가",
            "kosdaq_note": "성장주 혼조, 일부 테마 과열",
            "overseas_impact": "나스닥 및 반도체 지수 우호",
            "fx_rates_note": "달러/원 상승 부담은 관찰 필요",
            "major_events": "장후 미국 물가지표 발표 예정",
            "priority_sectors": "반도체, 전력기기",
            "avoid_sectors": "게임, 건설",
            "operating_principles": "A/B 후보만 진입 검토, 시초 과열 추격 금지",
        },
        "trade_date",
    )

    for row in [
        {"trade_date": DEMO_DATE, "sector_name": "반도체", "prior_move": "+2.3%", "volume_change": "+45%", "leader": "SK하이닉스", "laggards": "장비주", "news_note": "AI 서버 수요 기대", "overseas_linkage": "SOX 강세", "overheated": 0, "judgment": SectorJudgment.INTEREST.value},
        {"trade_date": DEMO_DATE, "sector_name": "전력기기", "prior_move": "+1.4%", "volume_change": "+20%", "leader": "HD현대일렉트릭", "laggards": "전선주", "news_note": "전력 인프라 투자", "overseas_linkage": "미국 인프라 기대", "overheated": 0, "judgment": SectorJudgment.INTEREST.value},
        {"trade_date": DEMO_DATE, "sector_name": "게임", "prior_move": "-1.1%", "volume_change": "-15%", "leader": "", "laggards": "중소형 게임", "news_note": "신작 모멘텀 부족", "overseas_linkage": "", "overheated": 0, "judgment": SectorJudgment.AVOID.value},
    ]:
        repo.upsert("sector_theme_map", row, "trade_date, sector_name")

    watch_rows = [
        {"trade_date": DEMO_DATE, "ticker": "000660", "name": "SK하이닉스", "market": Market.KOSPI.value, "sector_tags": "반도체,HBM", "grade": Grade.A.value, "bias": Bias.UPWARD.value, "score": 88, "thesis": "미국 반도체 강세와 전일 거래대금 증가", "risk_tags": "전고점 저항", "observation_price": "전일 고가", "alert_enabled": 1, "final_action": "entered"},
        {"trade_date": DEMO_DATE, "ticker": "042700", "name": "한미반도체", "market": Market.KOSPI.value, "sector_tags": "반도체,장비", "grade": Grade.B.value, "bias": Bias.UPWARD.value, "score": 74, "thesis": "섹터 후발주 관심", "risk_tags": "갭 과열", "observation_price": "VWAP", "alert_enabled": 1, "final_action": "held"},
        {"trade_date": DEMO_DATE, "ticker": "267260", "name": "HD현대일렉트릭", "market": Market.KOSPI.value, "sector_tags": "전력기기", "grade": Grade.C.value, "bias": Bias.WATCH.value, "score": 59, "thesis": "관심 섹터지만 가격 위치 부담", "risk_tags": "과열", "observation_price": "눌림", "alert_enabled": 0, "final_action": "ignored"},
        {"trade_date": DEMO_DATE, "ticker": "123456", "name": "예시게임", "market": Market.KOSDAQ.value, "sector_tags": "게임", "grade": Grade.EXCLUDED.value, "bias": Bias.NEUTRAL.value, "score": 35, "thesis": "회피 섹터", "risk_tags": "섹터 약세", "observation_price": "", "alert_enabled": 0, "final_action": "removed"},
    ]
    item_ids: dict[str, int] = {}
    for row in watch_rows:
        item_ids[row["ticker"]] = repo.upsert("premarket_watchlist", row, "trade_date, ticker")

    cards = [
        ("000660", 4, "시장 중립 이상", "반도체 관심", "AI 서버 수요", "기관 수급 관찰", "전고점 근처", "전고점 매물", "전일 고가/VWAP", "VWAP 회복 후 거래량 증가 시 검토", "VWAP 재이탈", "직전 저점 이탈", "시초 급등 추격 금지", "장중 +3.2%"),
        ("042700", 3, "시장 중립", "후발 장비주", "HBM 장비 관심", "", "갭 부담", "과열", "VWAP", "눌림 지지 확인", "시초가 이탈", "VWAP 재이탈", "5% 이상 갭 추격 금지", "보류"),
        ("267260", 2, "선별", "전력기기 관심", "인프라 투자", "", "고점 부담", "과열", "20일선", "관망", "섹터 약세", "", "신규 진입 금지", "무시"),
    ]
    for c in cards:
        repo.upsert(
            "stock_research_card",
            {
                "watchlist_item_id": item_ids[c[0]],
                "trade_date": DEMO_DATE,
                "ticker": c[0],
                "confidence": c[1],
                "market_evidence": c[2],
                "sector_evidence": c[3],
                "news_evidence": c[4],
                "supply_evidence": c[5],
                "chart_evidence": c[6],
                "risks": c[7],
                "price_structure": c[8],
                "scenario": c[9],
                "invalidation": c[10],
                "stop_criteria": c[11],
                "forbidden_conditions": c[12],
                "result_note": c[13],
            },
            "watchlist_item_id",
        )

    # Keep demo seeding idempotent for event-style rows that do not have natural keys.
    with repo.connect() as conn:
        conn.execute("DELETE FROM trade_execution_log WHERE trade_date=?", [DEMO_DATE])
        conn.execute("DELETE FROM user_decision_log WHERE trade_date=?", [DEMO_DATE])
        conn.execute("DELETE FROM intraday_signal_log WHERE trade_date=?", [DEMO_DATE])

    sig1 = create_generated_signal(repo, item_ids["000660"], "09:17", SignalType.VWAP_RECOVERY, 202000, "5분 평균 대비 증가")
    record_decision_for_signal(repo, sig1, "entered", "09:18", "조건 확인 후 소규모 진입 검토", "good")
    sig2 = create_generated_signal(repo, item_ids["042700"], "10:05", SignalType.PREV_HIGH_BREAK, 154000, "거래량 보통")
    record_decision_for_signal(repo, sig2, "held", "10:06", "갭 부담으로 보류", "normal")
    create_manual_note(repo, item_ids["267260"], "11:20", "C등급이라 알림 없이 관찰 메모만 기록")

    for row in [
        {"watchlist_item_id": item_ids["000660"], "trade_date": DEMO_DATE, "ticker": "000660", "grade": Grade.A.value, "bias": Bias.UPWARD.value, "day_high_return": 3.2, "day_low_return": -0.5, "close_return": 2.1, "bias_result": "correct", "signal_quality": "good", "execution_quality": "good", "failure_reason": "none", "improvement_note": "VWAP 회복 후 거래량 확인 유효"},
        {"watchlist_item_id": item_ids["042700"], "trade_date": DEMO_DATE, "ticker": "042700", "grade": Grade.B.value, "bias": Bias.UPWARD.value, "day_high_return": 1.2, "day_low_return": -1.0, "close_return": -0.2, "bias_result": "ambiguous", "signal_quality": "normal", "execution_quality": "normal", "failure_reason": "risk", "improvement_note": "갭 부담 시 보류 기준 유지"},
        {"watchlist_item_id": item_ids["267260"], "trade_date": DEMO_DATE, "ticker": "267260", "grade": Grade.C.value, "bias": Bias.WATCH.value, "day_high_return": 0.4, "day_low_return": -1.5, "close_return": -0.8, "bias_result": "correct", "signal_quality": "normal", "execution_quality": "good", "failure_reason": "none", "improvement_note": "C등급 관망 적절"},
    ]:
        repo.upsert("postmarket_review", row, "watchlist_item_id")
    return DEMO_DATE
