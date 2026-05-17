# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PULSAR is a locally-hosted cryptocurrency dashboard with live market data, technical analysis, ML-based scoring, and a virtual investment portfolio. It serves the top 10 coins by market cap from CoinGecko.

## Commands

```bash
# Run the server (development)
cd server && uvicorn main:app --reload --port 8000

# Or use the start script (port 8001, macOS caffeinate wrapper)
./start.sh

# Run all tests
pytest

# Run a single test file
pytest server/tests/test_indicators.py

# Run a single test by name
pytest server/tests/test_api.py::test_coins_endpoint

# Lint
ruff check server/
```

Install deps: `pip install -r requirements.txt` (runtime) and `pip install -r requirements-dev.txt` (test/lint).

## Environment variables

Copy `.env.example` to `.env` in the repo root before running. Key vars:

| Variable | Default | Notes |
|---|---|---|
| `PULSAR_SECRET_KEY` | `pulsar-dev-secret-change-before-deploying` | Change for any non-local deployment |
| `PULSAR_ADMIN_USERNAME` | `admin` | Seeded on first startup |
| `PULSAR_ADMIN_PASSWORD` | `admin` | Seeded on first startup |
| `PULSAR_TOKEN_EXPIRE_MINUTES` | `60` | JWT lifetime |

## Architecture

### Data flow

All market data lives in **module-level in-memory caches** inside `server/data.py`. On startup (`lifespan` in `main.py`), `init_data()` performs a blocking fetch of coins + OHLC, then APScheduler jobs keep caches warm:

- Coins: every 60 s
- OHLC (90-day candles): every 6 h
- Fear & Greed index: every 1 h
- ML scores: every 6 h
- News: every 30 min

Routes read from these caches directly — they never call external APIs inline (except `feargreed`/`news`, which fall back to a refresh if the cache is cold).

### Signal pipeline

`GET /api/coins` and `/api/signals` both compute per-coin signals inline:

1. `data.get_ohlc(coin_id)` → raw candles
2. `indicators.compute_indicators(ohlc)` → RSI-14, MACD(12,26,9), Bollinger Bands(20,2σ)
3. `indicators.compute_signal(indics, change_7d)` → weighted score (RSI 35%, MACD 35%, BB 20%, 7d trend 10%) → signal string
4. `ml.get_ml_score(coin_id)` → Ridge regression score (0–100, trained per-coin on OHLC history)
5. `_composite(signal_score, ml_score)` in `main.py` → 60% technical / 40% ML blended score

### Auth

JWT Bearer tokens via `python-jose`. `auth.py` handles token creation/decoding. `users.py` stores bcrypt-hashed passwords in `server/users.json` (created at runtime). The admin account is seeded on startup via `seed_admin()`. Non-admin routes use `get_current_user`; admin-only routes use `require_admin`.

### Portfolio persistence

Each user portfolio is a JSON file on disk: `server/portfolio_{username}.json` (default) or `server/portfolio_{username}_{name}.json` (named portfolios). `portfolio_history.py` appends daily snapshots to separate files. All portfolio files are stored inside `server/` at runtime — they are gitignored.

### Frontend

`frontend/index.html` is a single-file SPA (vanilla JS). FastAPI mounts it at `/` via `StaticFiles` after all `/api/*` routes are registered, so API routes always take precedence.

## Testing

Tests use FastAPI's `TestClient`. The `client` fixture in `conftest.py` patches all external API calls and redirects file I/O (users, portfolios, watchlists) to `tmp_path`, so tests are fully isolated and require no network access. The `auth_headers` fixture logs in as the seeded admin and returns Bearer headers.

`pyproject.toml` sets `pythonpath = ["server"]` so imports work without `sys.path` manipulation in test files.
