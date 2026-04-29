"""Account linking flow (/start)."""

from __future__ import annotations

import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from asgiref.sync import sync_to_async

from ..keyboards.menus import main_menu

router = Router(name="auth")


def _site_url() -> str:
    base = os.getenv("SITE_URL", "http://localhost:8080").strip()
    return base.rstrip("/")


@sync_to_async
def _ensure_profile(chat_id: int, username: str):
    from core.models import TelegramProfile

    profile = TelegramProfile.objects.filter(chat_id=chat_id).select_related("user").first()
    if profile is None:
        return None
    if username and profile.username != username:
        profile.username = username
        profile.save(update_fields=["username"])
    return profile


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if message.chat is None:
        return
    profile = await _ensure_profile(message.chat.id, message.from_user.username or "")
    if profile is None:
        await message.answer(
            "👋 Привет! Я бот KinNet — семейного органайзера.\n\n"
            "Чтобы привязать аккаунт, откройте сайт:\n"
            f"{_site_url()}/profile/\n\n"
            "После авторизации вернитесь и нажмите /start ещё раз.",
        )
        return

    if not profile.is_confirmed:
        link = f"{_site_url()}/telegram/confirm/{profile.confirm_token}/"
        await message.answer(
            "Аккаунт найден, осталось подтвердить привязку:\n" f"{link}",
        )
        return

    await message.answer(
        f"С возвращением, {profile.user.get_full_name() or profile.user.username}! "
        "Используйте меню ниже:",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(
        "<b>Команды KinNet:</b>\n"
        "/today — события и задачи на сегодня\n"
        "/events — ближайшие события\n"
        "/tasks — активные задачи\n"
        "/messages — последние сообщения семьи\n"
        "/families — мои семьи\n"
        "/help — эта справка"
    )


@router.message(F.text == "🔗 Привязка")
async def link_button(message: Message) -> None:
    await on_start(message)
