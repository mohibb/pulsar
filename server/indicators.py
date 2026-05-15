"""RSI, MACD, and Bollinger Bands computed from raw CoinGecko OHLC candles."""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe(val) -> Optional[float]:
    """Return float or None — treats NaN/Inf as None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _close_series(ohlc: list) -> Optional[pd.Series]:
    """Parse raw OHLC list into a time-sorted close-price Series."""
    if not ohlc or len(ohlc) < 30:
        return None
    df = pd.DataFrame(ohlc, columns=["ts", "open", "high", "low", "close"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df["close"].astype(float)


# ── Indicator primitives ──────────────────────────────────────────────────────


def _rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing: com = period - 1
    avg_gain = gain.ewm(com=period - 1, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return _safe((100.0 - 100.0 / (1.0 + rs)).iloc[-1])


def _macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        _safe(macd_line.iloc[-1]),
        _safe(signal_line.iloc[-1]),
        _safe(histogram.iloc[-1]),
    )


def _bbands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    sma = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=1)
    upper = _safe((sma + std_dev * std).iloc[-1])
    lower = _safe((sma - std_dev * std).iloc[-1])
    price = _safe(close.iloc[-1])
    if upper is None or lower is None or price is None:
        return None, None, None
    band_range = upper - lower
    bb_position = (price - lower) / band_range if band_range > 0 else 0.5
    return upper, lower, bb_position


# ── Public API ────────────────────────────────────────────────────────────────


def compute_indicators(ohlc: list) -> Optional[dict]:
    """
    Compute RSI-14, MACD (12,26,9), and Bollinger Bands (20,2) from OHLC candles.
    Each candle is [timestamp_ms, open, high, low, close].
    Returns None when fewer than 30 candles are provided.
    """
    close = _close_series(ohlc)
    if close is None:
        return None

    rsi = _rsi(close)
    macd, macd_sig, macd_hist = _macd(close)
    bb_upper, bb_lower, bb_position = _bbands(close)

    return {
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_sig,
        "macd_histogram": macd_hist,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_position": bb_position,
    }


def compute_signal(indicators: Optional[dict], change_7d: float) -> dict:
    """
    Weighted signal score from four inputs:
      RSI 35% | MACD crossover 35% | Bollinger position 20% | 7d trend 10%

    Score → signal mapping:
      75–100 → strong_buy | 60–74 → buy | 40–59 → neutral
      25–39  → caution    | 0–24  → sell
    """
    if indicators is None:
        return {
            "signal": "neutral",
            "signal_score": 50,
            "reasons": ["Insufficient historical data"],
        }

    reasons: list[str] = []
    weighted = 0.0
    weight_sum = 0.0

    # ── RSI (35%) ─────────────────────────────────────────────────────────────
    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < 30:
            rsi_score, note = 85, f"RSI oversold ({rsi:.1f}) — potential reversal"
        elif rsi > 70:
            rsi_score, note = 15, f"RSI overbought ({rsi:.1f}) — elevated risk"
        elif rsi < 45:
            rsi_score, note = 63, f"RSI recovering ({rsi:.1f})"
        elif rsi > 55:
            rsi_score, note = 37, f"RSI elevated ({rsi:.1f})"
        else:
            rsi_score, note = 50, f"RSI neutral ({rsi:.1f})"
        reasons.append(note)
        weighted += rsi_score * 0.35
        weight_sum += 0.35

    # ── MACD (35%) ────────────────────────────────────────────────────────────
    macd = indicators.get("macd")
    macd_sig = indicators.get("macd_signal")
    macd_hist = indicators.get("macd_histogram")
    if macd is not None and macd_sig is not None and macd_hist is not None:
        if macd > macd_sig and macd_hist > 0:
            macd_score, note = 75, "MACD bullish — above signal line"
        elif macd < macd_sig and macd_hist < 0:
            macd_score, note = 25, "MACD bearish — below signal line"
        else:
            macd_score, note = 50, "MACD near signal line"
        reasons.append(note)
        weighted += macd_score * 0.35
        weight_sum += 0.35

    # ── Bollinger Band position (20%) ─────────────────────────────────────────
    bb_pos = indicators.get("bb_position")
    if bb_pos is not None:
        # Linear: bb_pos=0 → score=80, bb_pos=0.5 → 50, bb_pos=1 → 20
        bb_score = max(10.0, min(90.0, 80.0 - 60.0 * bb_pos))
        if bb_pos < 0.2:
            reasons.append("Price near lower Bollinger Band — potential bounce")
        elif bb_pos > 0.8:
            reasons.append("Price near upper Bollinger Band — potential resistance")
        else:
            reasons.append(f"Price at {bb_pos:.0%} of Bollinger range")
        weighted += bb_score * 0.20
        weight_sum += 0.20

    # ── 7-day trend (10%) ─────────────────────────────────────────────────────
    if change_7d > 10:
        trend_score, note = 72, f"Strong 7d gain ({change_7d:+.1f}%)"
    elif change_7d > 3:
        trend_score, note = 60, f"Positive 7d trend ({change_7d:+.1f}%)"
    elif change_7d < -10:
        trend_score, note = 28, f"Sharp 7d decline ({change_7d:+.1f}%)"
    elif change_7d < -3:
        trend_score, note = 40, f"Negative 7d trend ({change_7d:+.1f}%)"
    else:
        trend_score, note = 50, f"Flat 7d trend ({change_7d:+.1f}%)"
    reasons.append(note)
    weighted += trend_score * 0.10
    weight_sum += 0.10

    signal_score = weighted / weight_sum if weight_sum else 50.0

    if signal_score >= 75:
        signal = "strong_buy"
    elif signal_score >= 60:
        signal = "buy"
    elif signal_score >= 40:
        signal = "neutral"
    elif signal_score >= 25:
        signal = "caution"
    else:
        signal = "sell"

    return {
        "signal": signal,
        "signal_score": round(signal_score, 1),
        "reasons": reasons,
    }
