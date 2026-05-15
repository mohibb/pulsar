import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(app) -> None:
    """Register background jobs and attach lifecycle hooks to the FastAPI app."""
    from data import refresh_coins, refresh_all_ohlc, refresh_feargreed

    scheduler.add_job(refresh_coins, "interval", seconds=60, id="refresh_coins")
    scheduler.add_job(refresh_all_ohlc, "interval", hours=6, id="refresh_ohlc")
    scheduler.add_job(
        lambda: asyncio.ensure_future(refresh_feargreed()),
        "interval",
        hours=1,
        id="refresh_feargreed",
    )

    @app.on_event("startup")
    async def _start():
        scheduler.start()
        await refresh_feargreed()
        logger.info("Scheduler started")

    @app.on_event("shutdown")
    async def _stop():
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
