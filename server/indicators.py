"""Technical indicator computation — stub for Phase 2."""

from typing import Optional


def compute_indicators(ohlc: list) -> Optional[dict]:
    """
    Phase 2 will populate this with RSI, MACD, and Bollinger Bands via pandas-ta.
    Returns None until implemented.
    """
    return None


def compute_signal(indicators: Optional[dict], change_7d: float) -> dict:
    """
    Phase 2 will implement weighted signal scoring.
    Returns a neutral placeholder until then.
    """
    return {
        "signal": "neutral",
        "signal_score": 50,
        "reasons": ["Indicator computation coming in Phase 2"],
    }
