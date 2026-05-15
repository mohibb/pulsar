"""Virtual portfolio logic — stub for Phase 3."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"

_INITIAL_CASH = 10_000.0


def _empty_portfolio() -> dict:
    return {
        "cash": _INITIAL_CASH,
        "initial_cash": _INITIAL_CASH,
        "holdings": {},
        "transactions": [],
    }


def load_portfolio() -> dict:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text())
        except Exception:
            pass
    return _empty_portfolio()


def save_portfolio(portfolio: dict) -> None:
    PORTFOLIO_FILE.write_text(json.dumps(portfolio, indent=2))


def reset_portfolio() -> dict:
    p = _empty_portfolio()
    save_portfolio(p)
    return p
