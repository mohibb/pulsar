import json
from datetime import date, timedelta

import pytest

import portfolio_history


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_history, "_HISTORY_DIR", tmp_path)


def test_load_empty():
    assert portfolio_history.load_history("bob") == []


def test_record_creates_entry():
    portfolio_history.record_snapshot("bob", 10_500.0, 500.0, 5.0)
    history = portfolio_history.load_history("bob")
    assert len(history) == 1
    assert history[0]["total_value"] == 10_500.0
    assert history[0]["cash"] == 500.0
    assert history[0]["pnl_pct"] == 5.0
    assert "date" in history[0]


def test_record_upserts_today():
    portfolio_history.record_snapshot("bob", 10_000.0, 1_000.0, 0.0)
    portfolio_history.record_snapshot("bob", 11_000.0, 900.0, 10.0)
    history = portfolio_history.load_history("bob")
    assert len(history) == 1
    assert history[0]["total_value"] == 11_000.0


def test_record_keeps_365_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_history, "_HISTORY_DIR", tmp_path)
    base = date(2020, 1, 1)
    fake = [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "total_value": float(10_000 + i),
            "cash": 1_000.0,
            "pnl_pct": float(i),
        }
        for i in range(400)
    ]
    portfolio_history._path("bob").write_text(json.dumps(fake))
    portfolio_history.record_snapshot("bob", 20_000.0, 500.0, 100.0)
    assert len(portfolio_history.load_history("bob")) == 365


def test_named_portfolio_separate_file():
    portfolio_history.record_snapshot("bob", 10_000.0, 1_000.0, 0.0, pf_name="trading")
    assert portfolio_history.load_history("bob") == []
    assert len(portfolio_history.load_history("bob", "trading")) == 1


def test_users_independent():
    portfolio_history.record_snapshot("alice", 12_000.0, 2_000.0, 20.0)
    portfolio_history.record_snapshot("bob", 8_000.0, 800.0, -20.0)
    assert portfolio_history.load_history("alice")[0]["total_value"] == 12_000.0
    assert portfolio_history.load_history("bob")[0]["total_value"] == 8_000.0


def test_path_default_no_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_history, "_HISTORY_DIR", tmp_path)
    p = portfolio_history._path("alice")
    assert "default" not in p.name
    assert p.name == "portfolio_history_alice.json"


def test_path_named_has_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_history, "_HISTORY_DIR", tmp_path)
    p = portfolio_history._path("alice", "trading")
    assert p.name == "portfolio_history_alice_trading.json"
