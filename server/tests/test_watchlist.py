import pytest

import watchlist


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_WATCHLIST_DIR", tmp_path)


def test_load_empty():
    assert watchlist.load_watchlist("bob") == []


def test_add_coin():
    result = watchlist.add_coin("bob", "bitcoin")
    assert result == ["bitcoin"]


def test_add_idempotent():
    watchlist.add_coin("bob", "bitcoin")
    result = watchlist.add_coin("bob", "bitcoin")
    assert result == ["bitcoin"]


def test_add_multiple():
    watchlist.add_coin("bob", "bitcoin")
    result = watchlist.add_coin("bob", "ethereum")
    assert result == ["bitcoin", "ethereum"]


def test_remove_coin():
    watchlist.add_coin("bob", "bitcoin")
    watchlist.add_coin("bob", "ethereum")
    result = watchlist.remove_coin("bob", "bitcoin")
    assert result == ["ethereum"]


def test_remove_nonexistent():
    result = watchlist.remove_coin("bob", "bitcoin")
    assert result == []


def test_users_independent():
    watchlist.add_coin("alice", "bitcoin")
    watchlist.add_coin("bob", "ethereum")
    assert watchlist.load_watchlist("alice") == ["bitcoin"]
    assert watchlist.load_watchlist("bob") == ["ethereum"]


def test_persist_across_load():
    watchlist.add_coin("bob", "bitcoin")
    assert "bitcoin" in watchlist.load_watchlist("bob")
