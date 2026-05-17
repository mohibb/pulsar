"""Per-user coin watchlist."""

from __future__ import annotations

import json
from pathlib import Path

_WATCHLIST_DIR = Path(__file__).parent


def _path(username: str) -> Path:
    return _WATCHLIST_DIR / f"watchlist_{username}.json"


def load_watchlist(username: str) -> list[str]:
    p = _path(username)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def add_coin(username: str, coin_id: str) -> list[str]:
    wl = load_watchlist(username)
    if coin_id not in wl:
        wl.append(coin_id)
        _path(username).write_text(json.dumps(wl))
    return wl


def remove_coin(username: str, coin_id: str) -> list[str]:
    wl = [c for c in load_watchlist(username) if c != coin_id]
    _path(username).write_text(json.dumps(wl))
    return wl
