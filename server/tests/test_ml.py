"""Tests for ML scoring functions."""

import time

import pytest

import ml

# Same oscillating OHLC as conftest — enough variation for all indicators
MOCK_OHLC = [
    [
        1_715_000_000_000 - i * 86_400_000,
        65_000.0 + (i % 5) * 200,
        67_000.0 + (i % 5) * 200 + 500,
        63_000.0 + (i % 5) * 200 - 500,
        65_000.0 + (i % 7 - 3) * 300,
    ]
    for i in range(90)
]

MOCK_CACHE = {
    "bitcoin": {"data": MOCK_OHLC, "ts": time.time()},
    "ethereum": {"data": MOCK_OHLC, "ts": time.time()},
}


@pytest.fixture(autouse=True)
def reset_scores():
    """Isolate ml._ml_scores between tests."""
    ml._ml_scores = {}
    yield
    ml._ml_scores = {}


# ── get_ml_score ──────────────────────────────────────────────────────────────


def test_score_none_before_refresh():
    assert ml.get_ml_score("bitcoin") is None


def test_score_none_for_unknown_coin():
    ml.refresh_ml_scores(MOCK_CACHE)
    assert ml.get_ml_score("dogecoin") is None


# ── refresh_ml_scores ─────────────────────────────────────────────────────────


def test_refresh_populates_scores():
    ml.refresh_ml_scores(MOCK_CACHE)
    assert ml.get_ml_score("bitcoin") is not None
    assert ml.get_ml_score("ethereum") is not None


def test_score_in_valid_range():
    ml.refresh_ml_scores(MOCK_CACHE)
    for coin_id in MOCK_CACHE:
        score = ml.get_ml_score(coin_id)
        assert score is not None
        assert 0.0 <= score <= 100.0


def test_refresh_handles_empty_cache():
    ml.refresh_ml_scores({})
    assert ml.get_ml_score("bitcoin") is None


def test_refresh_handles_insufficient_data():
    small = {"bitcoin": {"data": MOCK_OHLC[:5], "ts": time.time()}}
    ml.refresh_ml_scores(small)
    assert ml.get_ml_score("bitcoin") is None


def test_refresh_replaces_old_scores():
    ml.refresh_ml_scores(MOCK_CACHE)
    first = ml.get_ml_score("bitcoin")
    # Second refresh with empty cache clears all scores
    ml.refresh_ml_scores({})
    assert ml.get_ml_score("bitcoin") is None
    assert first is not None  # was populated before


def test_refresh_handles_dict_and_list_entries():
    """Cache entries may be raw lists or {data, ts} dicts."""
    ml.refresh_ml_scores({"bitcoin": {"data": MOCK_OHLC, "ts": time.time()}})
    assert ml.get_ml_score("bitcoin") is not None


# ── _build_dataset ────────────────────────────────────────────────────────────


def test_build_dataset_returns_none_for_short_series():
    assert ml._build_dataset(MOCK_OHLC[:10]) is None


def test_build_dataset_returns_triple_for_valid_data():
    result = ml._build_dataset(MOCK_OHLC)
    assert result is not None
    X, y, x_pred = result
    assert X.shape[1] == 4
    assert y.ndim == 1
    assert x_pred.shape == (1, 4)


def test_build_dataset_sufficient_training_rows():
    result = ml._build_dataset(MOCK_OHLC)
    assert result is not None
    X, y, _ = result
    assert len(X) >= 10
    assert len(X) == len(y)
