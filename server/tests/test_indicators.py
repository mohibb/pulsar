from indicators import compute_indicators, compute_signal

DUMMY_OHLC = [
    [1_715_000_000_000 - i * 86_400_000, 65_000.0, 67_000.0, 63_000.0, 66_000.0] for i in range(30)
]


def test_compute_indicators_returns_none_until_phase2():
    assert compute_indicators(DUMMY_OHLC) is None


def test_compute_indicators_none_on_empty():
    assert compute_indicators([]) is None


def test_compute_signal_neutral_placeholder():
    result = compute_signal(None, 0.0)
    assert result["signal"] == "neutral"
    assert result["signal_score"] == 50
    assert isinstance(result["reasons"], list)
    assert len(result["reasons"]) > 0


def test_compute_signal_required_keys():
    result = compute_signal(None, 5.0)
    assert {"signal", "signal_score", "reasons"} <= result.keys()


def test_compute_signal_score_in_range():
    result = compute_signal(None, -20.0)
    assert 0 <= result["signal_score"] <= 100
