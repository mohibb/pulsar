"""Tests for the plain-language recommendation engine."""

import pytest

from recommendation import bb_label, indicator_labels, macd_label, recommend, rsi_label


# ── rsi_label ─────────────────────────────────────────────────────────────────


def test_rsi_label_none():
    assert rsi_label(None) == ""


def test_rsi_label_oversold():
    assert "Oversold" in rsi_label(25)


def test_rsi_label_below_average():
    assert "Below average" in rsi_label(40)


def test_rsi_label_neutral():
    assert "Neutral" in rsi_label(50)


def test_rsi_label_healthy():
    assert "Healthy" in rsi_label(62)


def test_rsi_label_overbought():
    assert "Overbought" in rsi_label(75)


def test_rsi_label_includes_value():
    label = rsi_label(55)
    assert "55" in label


# ── macd_label ────────────────────────────────────────────────────────────────


def test_macd_label_none():
    assert macd_label(None) == ""


def test_macd_label_strong_uptrend():
    assert macd_label(100) == "Strong uptrend"


def test_macd_label_mild_uptrend():
    assert macd_label(10) == "Mild uptrend"


def test_macd_label_mild_downtrend():
    assert macd_label(-10) == "Mild downtrend"


def test_macd_label_strong_downtrend():
    assert macd_label(-100) == "Strong downtrend"


def test_macd_label_zero_is_mild_uptrend():
    # hist > 0 branch — zero falls to mild downtrend (not > 0)
    assert macd_label(0) == "Mild downtrend"


# ── bb_label ──────────────────────────────────────────────────────────────────


def test_bb_label_none():
    assert bb_label(None) == ""


def test_bb_label_near_support():
    assert "Near support" in bb_label(0.1)


def test_bb_label_lower_range():
    assert "Lower range" in bb_label(0.3)


def test_bb_label_mid_range():
    assert "Mid-range" in bb_label(0.5)


def test_bb_label_upper_range():
    assert "Upper range" in bb_label(0.7)


def test_bb_label_near_resistance():
    assert "Near resistance" in bb_label(0.9)


def test_bb_label_includes_percent():
    assert "%" in bb_label(0.5)


# ── indicator_labels ──────────────────────────────────────────────────────────


def test_indicator_labels_none():
    result = indicator_labels(None)
    assert result == {"rsi": "", "macd": "", "bb": ""}


def test_indicator_labels_empty():
    result = indicator_labels({})
    assert result == {"rsi": "", "macd": "", "bb": ""}


def test_indicator_labels_all_fields():
    result = indicator_labels({"rsi": 50, "macd_histogram": 20, "bb_position": 0.5})
    assert "Neutral" in result["rsi"]
    assert "Mild uptrend" in result["macd"]
    assert "Mid-range" in result["bb"]


# ── recommend() helpers ───────────────────────────────────────────────────────


def _portfolio(cash=10_000.0, holdings=None):
    return {
        "cash": cash,
        "initial_cash": 10_000.0,
        "holdings": holdings or {},
        "transactions": [],
    }


COINS = {
    "bitcoin": {"current_price": 50_000.0, "symbol": "btc", "name": "Bitcoin"},
    "ethereum": {"current_price": 3_000.0, "symbol": "eth", "name": "Ethereum"},
}


# ── recommend() ───────────────────────────────────────────────────────────────


def test_recommend_returns_required_keys():
    result = recommend(_portfolio(), COINS, {}, 10_000.0)
    assert "summary" in result
    assert "recommendations" in result
    assert "cash_pct" in result


def test_recommend_empty_portfolio_no_signals():
    result = recommend(_portfolio(), COINS, {}, 10_000.0)
    assert result["recommendations"] == []


def test_recommend_cash_pct_all_cash():
    result = recommend(_portfolio(cash=10_000.0), COINS, {}, 10_000.0)
    assert result["cash_pct"] == 100.0


def test_recommend_cash_pct_half_cash():
    result = recommend(_portfolio(cash=5_000.0), COINS, {}, 10_000.0)
    assert result["cash_pct"] == 50.0


def test_recommend_no_holdings_strong_signal_generates_buy():
    signals = {"bitcoin": {"composite_score": 75, "composite_verdict": "buy"}}
    result = recommend(_portfolio(cash=1_000.0), COINS, signals, 1_000.0)
    buys = [r for r in result["recommendations"] if r["action"] == "buy"]
    assert len(buys) == 1
    assert buys[0]["coin_id"] == "bitcoin"
    assert buys[0]["suggested_usd"] is not None


def test_recommend_no_holdings_sub70_score_no_buy():
    # Unowned coins need score >= 70; 65 should not trigger a buy.
    signals = {"bitcoin": {"composite_score": 65, "composite_verdict": "buy"}}
    result = recommend(_portfolio(cash=1_000.0), COINS, signals, 1_000.0)
    buys = [r for r in result["recommendations"] if r["action"] == "buy"]
    assert len(buys) == 0


def test_recommend_no_holdings_low_cash_no_buy():
    # cash < 50 threshold → unowned loop is skipped entirely
    signals = {"bitcoin": {"composite_score": 80, "composite_verdict": "buy"}}
    result = recommend(_portfolio(cash=30.0), COINS, signals, 30.0)
    buys = [r for r in result["recommendations"] if r["action"] == "buy"]
    assert len(buys) == 0


def test_recommend_hold_neutral_score():
    holdings = {"bitcoin": {"amount": 0.04, "avg_buy_price": 50_000.0}}
    signals = {"bitcoin": {"composite_score": 50, "composite_verdict": "hold"}}
    result = recommend(_portfolio(cash=8_000.0, holdings=holdings), COINS, signals, 10_000.0)
    assert result["recommendations"][0]["action"] == "hold"


def test_recommend_sell_bearish_with_profit():
    # bought at 40k, now 50k → +25% gain, bearish signal → sell
    holdings = {"bitcoin": {"amount": 0.1, "avg_buy_price": 40_000.0}}
    signals = {"bitcoin": {"composite_score": 20, "composite_verdict": "sell"}}
    result = recommend(_portfolio(cash=5_000.0, holdings=holdings), COINS, signals, 10_000.0)
    rec = result["recommendations"][0]
    assert rec["action"] == "sell"
    assert rec["suggested_usd"] == pytest.approx(2_500.0)


def test_recommend_sell_bearish_with_large_loss():
    # bought at 70k, now 50k → -28.6% loss, bearish signal → sell
    holdings = {"bitcoin": {"amount": 0.1, "avg_buy_price": 70_000.0}}
    signals = {"bitcoin": {"composite_score": 20, "composite_verdict": "sell"}}
    result = recommend(_portfolio(cash=5_000.0, holdings=holdings), COINS, signals, 10_000.0)
    rec = result["recommendations"][0]
    assert rec["action"] == "sell"
    assert rec["suggested_usd"] is not None


def test_recommend_hold_bearish_near_breakeven():
    # bought at 49k, now 50k → ~+2%, not triggering either sell threshold
    holdings = {"bitcoin": {"amount": 0.1, "avg_buy_price": 49_000.0}}
    signals = {"bitcoin": {"composite_score": 20, "composite_verdict": "sell"}}
    result = recommend(_portfolio(cash=5_000.0, holdings=holdings), COINS, signals, 10_000.0)
    assert result["recommendations"][0]["action"] == "hold"


def test_recommend_buy_held_coin_strong_signal():
    # small BTC holding, lots of cash, strong signal → buy more
    holdings = {"bitcoin": {"amount": 0.01, "avg_buy_price": 50_000.0}}
    signals = {"bitcoin": {"composite_score": 65, "composite_verdict": "buy"}}
    result = recommend(_portfolio(cash=5_000.0, holdings=holdings), COINS, signals, 5_500.0)
    rec = result["recommendations"][0]
    assert rec["action"] == "buy"
    assert rec["suggested_usd"] is not None


def test_recommend_hold_when_strong_but_no_cash():
    # strong signal but no cash to deploy
    holdings = {"bitcoin": {"amount": 0.2, "avg_buy_price": 50_000.0}}
    signals = {"bitcoin": {"composite_score": 65, "composite_verdict": "buy"}}
    result = recommend(_portfolio(cash=5.0, holdings=holdings), COINS, signals, 10_005.0)
    assert result["recommendations"][0]["action"] == "hold"


def test_recommend_summary_is_nonempty_string():
    result = recommend(_portfolio(), COINS, {}, 10_000.0)
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 10


def test_recommend_rec_fields():
    holdings = {"bitcoin": {"amount": 0.04, "avg_buy_price": 50_000.0}}
    signals = {"bitcoin": {"composite_score": 50, "composite_verdict": "hold"}}
    result = recommend(_portfolio(cash=8_000.0, holdings=holdings), COINS, signals, 10_000.0)
    rec = result["recommendations"][0]
    for key in (
        "coin_id",
        "symbol",
        "name",
        "action",
        "plain",
        "detail",
        "current_value",
        "pnl_pct",
        "position_pct",
        "composite_score",
    ):
        assert key in rec
