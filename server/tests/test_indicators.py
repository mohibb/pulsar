from indicators import compute_indicators, compute_signal

# 90 candles with enough price variation for all indicators to be non-NaN
DUMMY_OHLC = [
    [
        1_715_000_000_000 - i * 86_400_000,
        65_000.0 + (i % 5) * 200,
        67_000.0 + (i % 5) * 200 + 500,
        63_000.0 + (i % 5) * 200 - 500,
        65_000.0 + (i % 7 - 3) * 300,
    ]
    for i in range(90)
]

INDICATOR_KEYS = (
    "rsi",
    "macd",
    "macd_signal",
    "macd_histogram",
    "bb_upper",
    "bb_lower",
    "bb_position",
)


# ── compute_indicators ────────────────────────────────────────────────────────


def test_returns_none_for_empty_input():
    assert compute_indicators([]) is None


def test_returns_none_for_insufficient_data():
    assert compute_indicators(DUMMY_OHLC[:10]) is None


def test_returns_dict_with_sufficient_data():
    assert isinstance(compute_indicators(DUMMY_OHLC), dict)


def test_has_all_required_keys():
    result = compute_indicators(DUMMY_OHLC)
    assert result is not None
    for key in INDICATOR_KEYS:
        assert key in result


def test_rsi_in_valid_range():
    result = compute_indicators(DUMMY_OHLC)
    assert result is not None
    rsi = result["rsi"]
    if rsi is not None:
        assert 0.0 <= rsi <= 100.0


def test_bb_upper_greater_than_lower():
    result = compute_indicators(DUMMY_OHLC)
    assert result is not None
    upper, lower = result["bb_upper"], result["bb_lower"]
    if upper is not None and lower is not None:
        assert upper > lower


def test_bb_position_roughly_in_range():
    result = compute_indicators(DUMMY_OHLC)
    assert result is not None
    pos = result["bb_position"]
    # Percent-B can briefly exceed [0,1] in trending markets; allow ±0.5 margin
    if pos is not None:
        assert -0.5 <= pos <= 1.5


def test_macd_histogram_equals_macd_minus_signal():
    result = compute_indicators(DUMMY_OHLC)
    assert result is not None
    macd = result["macd"]
    sig = result["macd_signal"]
    hist = result["macd_histogram"]
    if macd is not None and sig is not None and hist is not None:
        assert abs(hist - (macd - sig)) < 1e-6


# ── compute_signal ────────────────────────────────────────────────────────────


def test_signal_has_required_keys():
    result = compute_signal(None, 0.0)
    assert {"signal", "signal_score", "reasons"} <= result.keys()


def test_signal_neutral_when_no_indicators():
    result = compute_signal(None, 0.0)
    assert result["signal"] == "neutral"
    assert result["signal_score"] == 50


def test_signal_score_in_range():
    for change_7d in (-20.0, -5.0, 0.0, 5.0, 20.0):
        result = compute_signal(None, change_7d)
        assert 0 <= result["signal_score"] <= 100


def test_signal_verdict_is_valid():
    result = compute_signal(compute_indicators(DUMMY_OHLC), 0.0)
    assert result["signal"] in ("strong_buy", "buy", "neutral", "caution", "sell")


def test_signal_has_reasons():
    result = compute_signal(compute_indicators(DUMMY_OHLC), 2.0)
    assert len(result["reasons"]) > 0


def test_oversold_rsi_raises_score():
    indicators = {k: None for k in INDICATOR_KEYS}
    indicators["rsi"] = 22.0
    result = compute_signal(indicators, 0.0)
    assert result["signal_score"] > 50


def test_overbought_rsi_lowers_score():
    indicators = {k: None for k in INDICATOR_KEYS}
    indicators["rsi"] = 82.0
    result = compute_signal(indicators, 0.0)
    assert result["signal_score"] < 50


def test_bullish_macd_raises_score():
    indicators = {k: None for k in INDICATOR_KEYS}
    indicators.update({"macd": 100.0, "macd_signal": 80.0, "macd_histogram": 20.0})
    result = compute_signal(indicators, 0.0)
    assert result["signal_score"] > 50


def test_bearish_macd_lowers_score():
    indicators = {k: None for k in INDICATOR_KEYS}
    indicators.update({"macd": -100.0, "macd_signal": -80.0, "macd_histogram": -20.0})
    result = compute_signal(indicators, 0.0)
    assert result["signal_score"] < 50


def test_strong_positive_7d_raises_score():
    # Pass an all-None dict (not None) so the 7d branch runs instead of short-circuiting
    no_indicators = {k: None for k in INDICATOR_KEYS}
    result_strong = compute_signal(no_indicators, 15.0)
    result_flat = compute_signal(no_indicators, 0.0)
    assert result_strong["signal_score"] > result_flat["signal_score"]


def test_strong_negative_7d_lowers_score():
    no_indicators = {k: None for k in INDICATOR_KEYS}
    result_drop = compute_signal(no_indicators, -15.0)
    result_flat = compute_signal(no_indicators, 0.0)
    assert result_drop["signal_score"] < result_flat["signal_score"]
