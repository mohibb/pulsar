"""Virtual portfolio — per-user JSON persistence."""

import json
from pathlib import Path

_PORTFOLIO_DIR = Path(__file__).parent
_INITIAL_CASH = 10_000.0


def _path(username: str) -> Path:
    return _PORTFOLIO_DIR / f"portfolio_{username}.json"


def _empty() -> dict:
    return {
        "cash": _INITIAL_CASH,
        "initial_cash": _INITIAL_CASH,
        "holdings": {},
        "transactions": [],
    }


def load_portfolio(username: str) -> dict:
    p = _path(username)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return _empty()


def save_portfolio(username: str, portfolio: dict) -> None:
    _path(username).write_text(json.dumps(portfolio, indent=2))


def reset_portfolio(username: str) -> dict:
    fresh = _empty()
    save_portfolio(username, fresh)
    return fresh
