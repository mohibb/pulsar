"""Signal backtesting against historical OHLC data."""

from __future__ import annotations

from datetime import datetime, timezone

from indicators import compute_indicators, compute_signal

_FORWARD_DAYS = 7
_MIN_HISTORY = 35


def _stats(returns: list[float]) -> dict:
    if not returns:
        return {"count": 0, "win_rate": None, "avg_return": None}
    wins = sum(1 for r in returns if r > 0)
    return {
        "count": len(returns),
        "win_rate": round(wins / len(returns) * 100, 1),
        "avg_return": round(sum(returns) / len(returns), 2),
    }


def run_backtest(ohlc: list, forward_days: int = _FORWARD_DAYS) -> dict:
    """
    Walk through historical OHLC candles, compute the signal at each step
    using only data available at that point, then measure the actual price
    return over the following forward_days.
    """
    candles = sorted(ohlc, key=lambda c: c[0])
    records = []

    for i in range(_MIN_HISTORY, len(candles) - forward_days):
        indics = compute_indicators(candles[: i + 1])
        if not indics:
            continue
        prev7_close = candles[i - 7][4] if i >= 7 else candles[0][4]
        curr_close = candles[i][4]
        change_7d = (curr_close - prev7_close) / prev7_close * 100 if prev7_close else 0.0

        sig = compute_signal(indics, change_7d)
        entry = candles[i][4]
        exit_ = candles[i + forward_days][4]
        fwd_return = (exit_ - entry) / entry * 100 if entry else 0.0

        records.append(
            {
                "date": datetime.fromtimestamp(candles[i][0] / 1000, tz=timezone.utc)
                .date()
                .isoformat(),
                "signal": sig["signal"],
                "signal_score": round(sig["signal_score"], 1),
                "entry_price": round(entry, 2),
                "fwd_return": round(fwd_return, 2),
            }
        )

    buy_ret = [r["fwd_return"] for r in records if r["signal"] in ("buy", "strong_buy")]
    sell_ret = [r["fwd_return"] for r in records if r["signal"] in ("sell", "caution")]
    hold_ret = [r["fwd_return"] for r in records if r["signal"] == "neutral"]

    return {
        "forward_days": forward_days,
        "total_signals": len(records),
        "buy": _stats(buy_ret),
        "sell": _stats(sell_ret),
        "hold": _stats(hold_ret),
        "recent": records[-30:],
    }
