import asyncio
import logging
import os
from dotenv import load_dotenv
import uvicorn
from aiogram import Bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    db_url = os.environ["DATABASE_URL"]
    mini_app_url = os.environ["MINI_APP_URL"]
    superadmin_id_str = os.environ.get("SUPERADMIN_CHAT_ID")
    superadmin_id = int(superadmin_id_str) if superadmin_id_str else None
    poll_interval = float(os.environ.get("POLL_INTERVAL_SECONDS", "1.5"))
    port = int(os.environ.get("PORT", os.environ.get("API_PORT", "8000")))

    if not (1.0 <= poll_interval <= 10.0):
        raise ValueError(f"POLL_INTERVAL_SECONDS must be between 1.0 and 10.0, got {poll_interval}")

    from backend.db import create_pool, create_schema, seed_initial_data
    pool = await create_pool(db_url)
    await create_schema(pool)
    await seed_initial_data(pool, poll_interval=poll_interval, superadmin_id=superadmin_id)
    logger.info("Database ready")

    bot = Bot(token=token)

    from backend.api.app import create_app
    app = create_app(pool=pool)
    app.state.bot = bot  # required by /api/admin/broadcast
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    from backend.bot import make_dispatcher
    dp = make_dispatcher(pool=pool, mini_app_url=mini_app_url)

    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    from backend.oref_poller import OrefPoller
    from backend.notifier import Notifier
    poller = OrefPoller(queue=queue, interval=poll_interval)
    notifier = Notifier(bot=bot, pool=pool)

    async def run_bot():
        await dp.start_polling(bot)

    async def run_notifier():
        await notifier.run(queue)

    logger.info("Starting all tasks on port %s", port)
    await asyncio.gather(
        server.serve(),
        poller.run(),
        run_notifier(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
