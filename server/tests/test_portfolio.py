import portfolio


def test_empty_portfolio_shape():
    p = portfolio._empty_portfolio()
    assert p["cash"] == 10_000.0
    assert p["initial_cash"] == 10_000.0
    assert p["holdings"] == {}
    assert p["transactions"] == []


def test_load_portfolio_returns_fresh_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", tmp_path / "portfolio.json")
    p = portfolio.load_portfolio()
    assert p["cash"] == 10_000.0
    assert p["holdings"] == {}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", tmp_path / "portfolio.json")
    original = portfolio._empty_portfolio()
    original["cash"] = 5_000.0
    original["holdings"]["bitcoin"] = {"amount": 0.05, "avg_buy_price": 60_000.0}
    portfolio.save_portfolio(original)

    loaded = portfolio.load_portfolio()
    assert loaded["cash"] == 5_000.0
    assert loaded["holdings"]["bitcoin"]["amount"] == 0.05


def test_reset_clears_holdings(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", tmp_path / "portfolio.json")
    p = portfolio._empty_portfolio()
    p["cash"] = 100.0
    p["holdings"]["bitcoin"] = {"amount": 0.1, "avg_buy_price": 50_000.0}
    portfolio.save_portfolio(p)

    reset = portfolio.reset_portfolio()
    assert reset["cash"] == 10_000.0
    assert reset["holdings"] == {}

    # Confirm persisted
    loaded = portfolio.load_portfolio()
    assert loaded["cash"] == 10_000.0


def test_load_portfolio_handles_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", tmp_path / "portfolio.json")
    (tmp_path / "portfolio.json").write_text("not valid json {{")
    p = portfolio.load_portfolio()
    assert p["cash"] == 10_000.0
