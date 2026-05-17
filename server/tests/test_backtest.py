from backtest import run_backtest
from tests.conftest import MOCK_OHLC


def test_required_keys():
    result = run_backtest(MOCK_OHLC)
    for key in ("forward_days", "total_signals", "buy", "sell", "hold", "recent"):
        assert key in result


def test_stats_structure():
    result = run_backtest(MOCK_OHLC)
    for key in ("buy", "sell", "hold"):
        stats = result[key]
        assert "count" in stats
        assert "win_rate" in stats
        assert "avg_return" in stats


def test_win_rate_range():
    result = run_backtest(MOCK_OHLC)
    for key in ("buy", "sell", "hold"):
        wr = result[key]["win_rate"]
        if wr is not None:
            assert 0 <= wr <= 100


def test_recent_max_30():
    result = run_backtest(MOCK_OHLC)
    assert len(result["recent"]) <= 30


def test_recent_record_keys():
    result = run_backtest(MOCK_OHLC)
    for rec in result["recent"]:
        for key in ("date", "signal", "signal_score", "entry_price", "fwd_return"):
            assert key in rec


def test_forward_days_param():
    result = run_backtest(MOCK_OHLC, forward_days=3)
    assert result["forward_days"] == 3


def test_insufficient_data_returns_zero_signals():
    tiny = [[i * 86_400_000, 100.0, 110.0, 90.0, 100.0] for i in range(10)]
    result = run_backtest(tiny)
    assert result["total_signals"] == 0


def test_empty_stats_when_no_signals():
    tiny = [[i * 86_400_000, 100.0, 110.0, 90.0, 100.0] for i in range(10)]
    result = run_backtest(tiny)
    assert result["buy"]["count"] == 0
    assert result["buy"]["win_rate"] is None


def test_produces_signals_with_enough_data():
    result = run_backtest(MOCK_OHLC)
    assert result["total_signals"] > 0
