"""Aiogram v3 entrypoint for the KinNet Telegram bot.

Runs in webhook mode when ``TELEGRAM_WEBHOOK_URL`` is set, otherwise falls
back to long polling. Webhook deployments expose ``/webhook/<secret>`` from
``aiohttp``; mount it behind Nginx in production.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .django_setup import setup_django

setup_django()

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402

from .handlers import router as root_router  # noqa: E402

logger = logging.getLogger(__name__)


def _make_bot_and_dp() -> tuple[Bot, Dispatcher]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set; cannot start bot.")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(root_router)
    return bot, dp


async def _run_polling() -> None:
    bot, dp = _make_bot_and_dp()
    logger.info("KinNet bot starting in long-polling mode")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def _run_webhook() -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot, dp = _make_bot_and_dp()
    webhook_url = os.environ["TELEGRAM_WEBHOOK_URL"].rstrip("/")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "kinnet")
    path = f"/webhook/{secret}"

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(app, path=path)
    setup_application(app, dp, bot=bot)

    async def _on_startup(_app):
        await bot.set_webhook(f"{webhook_url}{path}", secret_token=secret)
        logger.info("Webhook set: %s%s", webhook_url, path)

    async def _on_shutdown(_app):
        await bot.delete_webhook()

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("BOT_WEBHOOK_PORT", "8081")))
    await site.start()
    logger.info("KinNet bot webhook server listening on :%s", os.getenv("BOT_WEBHOOK_PORT", "8081"))
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if os.getenv("TELEGRAM_WEBHOOK_URL"):
        asyncio.run(_run_webhook())
    else:
        asyncio.run(_run_polling())


if __name__ == "__main__":
    main()
