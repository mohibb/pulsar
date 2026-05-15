import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data import (
    get_coins_cache,
    get_ohlc,
    get_feargreed_cache,
    get_coin_price,
    init_data,
    refresh_feargreed,
)
from indicators import compute_indicators, compute_signal
from ml import get_ml_score
from portfolio import load_portfolio, save_portfolio, reset_portfolio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — fetching initial data…")
    init_data()
    await refresh_feargreed()
    from scheduler import scheduler

    scheduler.add_job(
        __import__("data").refresh_coins,
        "interval",
        seconds=60,
        id="refresh_coins",
        replace_existing=True,
    )
    scheduler.add_job(
        __import__("data").refresh_all_ohlc,
        "interval",
        hours=6,
        id="refresh_ohlc",
        replace_existing=True,
    )
    import asyncio

    scheduler.add_job(
        lambda: asyncio.ensure_future(refresh_feargreed()),
        "interval",
        hours=1,
        id="refresh_feargreed",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Pulsar", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_coin_response(raw: dict) -> dict:
    coin_id = raw["id"]
    ohlc = get_ohlc(coin_id)
    indicators = compute_indicators(ohlc) if ohlc else None
    change_7d = raw.get("price_change_percentage_7d_in_currency") or 0.0
    signal_data = compute_signal(indicators, change_7d)

    return {
        "id": coin_id,
        "symbol": raw["symbol"],
        "name": raw["name"],
        "image": raw.get("image"),
        "price": raw["current_price"],
        "market_cap": raw["market_cap"],
        "market_cap_rank": raw["market_cap_rank"],
        "volume_24h": raw["total_volume"],
        "change_24h": raw.get("price_change_percentage_24h") or 0.0,
        "change_7d": change_7d,
        "indicators": indicators,
        "signal": signal_data["signal"],
        "signal_reasons": signal_data["reasons"],
    }


def _composite_score(signal_score: float, ml_score) -> tuple[float, str, str]:
    if ml_score is not None:
        score = signal_score * 0.6 + ml_score * 0.4
    else:
        score = float(signal_score)

    if score >= 60:
        verdict, label = "buy", "Buy"
    elif score >= 40:
        verdict, label = "hold", "Hold"
    else:
        verdict, label = "sell", "Sell"

    return score, verdict, label


def _feargreed_market_score(fg_value: int, coins_cache: dict) -> dict:
    """Very basic market score — full logic lands in Phase 2."""
    # Fear & Greed component (inverted at extremes): high greed lowers score
    if fg_value <= 25:
        fg_component = 75
    elif fg_value >= 75:
        fg_component = 25
    else:
        fg_component = 50 + (50 - fg_value) * 0.5

    score = round(fg_component)

    if score >= 60:
        verdict, label = "buy", "Buy"
    elif score >= 40:
        verdict, label = "neutral", "Neutral"
    else:
        verdict, label = "caution", "Cautious"

    return {
        "score": score,
        "verdict": verdict,
        "verdict_label": label,
        "reasons": ["Market score detail coming in Phase 2"],
    }


def _feargreed_interpretation(value: int, trend: int) -> str:
    if value >= 75:
        base = "The market is in extreme greed territory."
    elif value >= 55:
        base = "The market is showing greed."
    elif value >= 45:
        base = "Sentiment is roughly neutral."
    elif value >= 25:
        base = "The market is showing fear."
    else:
        base = "The market is in extreme fear territory."

    if trend > 10:
        context = " Sentiment has risen sharply recently — historically a warning sign."
    elif trend < -10:
        context = " Sentiment has dropped notably — could indicate a capitulation opportunity."
    else:
        context = " Sentiment has been relatively stable."

    return base + context


# ── Routes ───────────────────────────────────────────────────────────────────


@app.get("/api/coins")
def api_coins():
    cache, ts = get_coins_cache()
    if not cache:
        raise HTTPException(503, "Coin data not yet available")
    coins = [_build_coin_response(raw) for raw in cache.values()]
    return {
        "updated_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "coins": coins,
    }


@app.get("/api/market")
def api_market():
    cache, _ = get_coins_cache()
    if not cache:
        raise HTTPException(503, "Coin data not yet available")

    coins = list(cache.values())
    total_market_cap = sum(c.get("market_cap") or 0 for c in coins)
    total_volume = sum(c.get("total_volume") or 0 for c in coins)

    btc = cache.get("bitcoin", {})
    eth = cache.get("ethereum", {})
    btc_dom = (
        round((btc.get("market_cap") or 0) / total_market_cap * 100, 1) if total_market_cap else 0
    )
    eth_dom = (
        round((eth.get("market_cap") or 0) / total_market_cap * 100, 1) if total_market_cap else 0
    )

    changes = [c.get("price_change_percentage_24h") or 0.0 for c in coins]
    advancing = sum(1 for ch in changes if ch > 0)
    declining = sum(1 for ch in changes if ch < 0)
    avg_change = round(sum(changes) / len(changes), 2) if changes else 0.0

    return {
        "total_market_cap": total_market_cap,
        "total_volume_24h": total_volume,
        "btc_dominance": btc_dom,
        "eth_dominance": eth_dom,
        "avg_change_24h": avg_change,
        "advancing": advancing,
        "declining": declining,
    }


@app.get("/api/feargreed")
async def api_feargreed():
    cache, ts = get_feargreed_cache()
    if not cache:
        await refresh_feargreed()
        cache, ts = get_feargreed_cache()
    if not cache:
        raise HTTPException(503, "Fear & Greed data not yet available")

    data_points = cache.get("data", [])
    if not data_points:
        raise HTTPException(503, "Fear & Greed data empty")

    today = data_points[0]
    value = int(today["value"])
    classification = today["value_classification"]

    yesterday_val = int(data_points[1]["value"]) if len(data_points) > 1 else value
    last_week_val = int(data_points[6]["value"]) if len(data_points) > 6 else value
    trend = value - yesterday_val

    history = [
        {
            "date": dp.get("timestamp", ""),
            "value": int(dp["value"]),
            "classification": dp["value_classification"],
        }
        for dp in data_points
    ]

    coins_cache, _ = get_coins_cache()
    market_score = _feargreed_market_score(value, coins_cache)
    interpretation = _feargreed_interpretation(value, value - last_week_val)

    return {
        "value": value,
        "classification": classification,
        "yesterday": yesterday_val,
        "last_week": last_week_val,
        "trend": trend,
        "history": history,
        "interpretation": interpretation,
        "market_score": market_score,
    }


@app.get("/api/history/{coin_id}")
def api_history(coin_id: str):
    ohlc = get_ohlc(coin_id)
    if ohlc is None:
        raise HTTPException(404, f"No history for {coin_id}")

    data = [
        {
            "date": datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc).date().isoformat(),
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
        }
        for candle in ohlc
    ]
    return {"coin_id": coin_id, "days": 90, "data": data}


@app.get("/api/signals")
def api_signals():
    cache, ts = get_coins_cache()
    if not cache:
        raise HTTPException(503, "Coin data not yet available")

    signals = []
    for coin_id, raw in cache.items():
        ohlc = get_ohlc(coin_id)
        indicators = compute_indicators(ohlc) if ohlc else None
        change_7d = raw.get("price_change_percentage_7d_in_currency") or 0.0
        sig = compute_signal(indicators, change_7d)
        ml_score = get_ml_score(coin_id)
        comp_score, comp_verdict, comp_label = _composite_score(sig["signal_score"], ml_score)

        signals.append(
            {
                "coin_id": coin_id,
                "symbol": raw["symbol"],
                "signal": sig["signal"],
                "signal_score": sig["signal_score"],
                "ml_score": ml_score,
                "composite_score": round(comp_score, 1),
                "composite_verdict": comp_verdict,
                "composite_label": comp_label,
                "reasons": sig["reasons"],
            }
        )

    return {
        "updated_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "signals": signals,
    }


@app.get("/api/portfolio")
def api_portfolio():
    from data import get_coins_cache

    portfolio = load_portfolio()
    coins_cache, _ = get_coins_cache()

    holdings_list = []
    total_holdings_value = 0.0

    for coin_id, h in portfolio["holdings"].items():
        coin = coins_cache.get(coin_id, {})
        current_price = coin.get("current_price") or h["avg_buy_price"]
        value = h["amount"] * current_price
        pnl = value - h["amount"] * h["avg_buy_price"]
        pnl_pct = (current_price - h["avg_buy_price"]) / h["avg_buy_price"] * 100

        holdings_list.append(
            {
                "coin_id": coin_id,
                "symbol": coin.get("symbol", coin_id),
                "amount": h["amount"],
                "avg_buy_price": h["avg_buy_price"],
                "current_price": current_price,
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )
        total_holdings_value += value

    total_value = portfolio["cash"] + total_holdings_value
    total_pnl = total_value - portfolio["initial_cash"]
    total_pnl_pct = total_pnl / portfolio["initial_cash"] * 100

    return {
        "cash": round(portfolio["cash"], 2),
        "initial_cash": portfolio["initial_cash"],
        "holdings": holdings_list,
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "transactions": list(reversed(portfolio["transactions"])),
    }


@app.post("/api/portfolio/buy")
def api_portfolio_buy(body: dict):
    coin_id = body.get("coin_id")
    usd_amount = float(body.get("usd_amount", 0))

    if usd_amount < 1:
        raise HTTPException(400, "Minimum trade is $1")

    price = get_coin_price(coin_id)
    if price is None:
        raise HTTPException(404, f"Unknown coin: {coin_id}")

    portfolio = load_portfolio()
    if usd_amount > portfolio["cash"]:
        raise HTTPException(400, "Insufficient cash")

    amount = usd_amount / price
    holding = portfolio["holdings"].get(coin_id)
    if holding:
        total_amount = holding["amount"] + amount
        holding["avg_buy_price"] = (
            holding["amount"] * holding["avg_buy_price"] + amount * price
        ) / total_amount
        holding["amount"] = total_amount
    else:
        portfolio["holdings"][coin_id] = {"amount": amount, "avg_buy_price": price}

    portfolio["cash"] -= usd_amount
    portfolio["transactions"].append(
        {
            "id": f"txn_{len(portfolio['transactions']) + 1:04d}",
            "type": "buy",
            "coin_id": coin_id,
            "amount": amount,
            "price": price,
            "total": usd_amount,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    )
    save_portfolio(portfolio)
    return api_portfolio()


@app.post("/api/portfolio/sell")
def api_portfolio_sell(body: dict):
    coin_id = body.get("coin_id")
    usd_amount = float(body.get("usd_amount", 0))

    if usd_amount < 1:
        raise HTTPException(400, "Minimum trade is $1")

    price = get_coin_price(coin_id)
    if price is None:
        raise HTTPException(404, f"Unknown coin: {coin_id}")

    portfolio = load_portfolio()
    holding = portfolio["holdings"].get(coin_id)
    if not holding:
        raise HTTPException(400, f"No holding for {coin_id}")

    holding_value = holding["amount"] * price
    if usd_amount > holding_value:
        raise HTTPException(400, "Cannot sell more than current holding value")

    amount_to_sell = usd_amount / price
    holding["amount"] -= amount_to_sell
    if holding["amount"] < 1e-10:
        del portfolio["holdings"][coin_id]

    portfolio["cash"] += usd_amount
    portfolio["transactions"].append(
        {
            "id": f"txn_{len(portfolio['transactions']) + 1:04d}",
            "type": "sell",
            "coin_id": coin_id,
            "amount": amount_to_sell,
            "price": price,
            "total": usd_amount,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    )
    save_portfolio(portfolio)
    return api_portfolio()


@app.post("/api/portfolio/reset")
def api_portfolio_reset():
    reset_portfolio()
    return api_portfolio()
