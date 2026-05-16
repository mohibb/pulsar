"""Per-user daily portfolio value snapshots (one per day, kept 365 days)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_HISTORY_DIR = Path(__file__).parent


def _path(username: str, pf_name: str = "default") -> Path:
    suffix = "" if pf_name == "default" else f"_{pf_name}"
    return _HISTORY_DIR / f"portfolio_history_{username}{suffix}.json"


def load_history(username: str, pf_name: str = "default") -> list[dict]:
    p = _path(username, pf_name)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def record_snapshot(
    username: str,
    total_value: float,
    cash: float,
    pnl_pct: float,
    pf_name: str = "default",
) -> None:
    """Upsert today's snapshot. Safe to call on every portfolio read."""
    history = load_history(username, pf_name)
    today = date.today().isoformat()
    history = [h for h in history if h["date"] != today]
    history.append(
        {
            "date": today,
            "total_value": round(total_value, 2),
            "cash": round(cash, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
    )
    history = sorted(history, key=lambda x: x["date"])[-365:]
    _path(username, pf_name).write_text(json.dumps(history))
