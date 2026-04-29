"""Account linking flow (/start)."""

from __future__ import annotations

import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from asgiref.sync import sync_to_async

from core.tasks import tg_escape

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


@sync_to_async
def _link_account(chat_id: int, tg_username: str, target_username: str):
    """Create or refresh a ``TelegramProfile`` for the given Django username.

    Returns a tuple ``(status, payload)`` where ``status`` is one of:

    * ``"already_linked"`` — chat already linked to a different Django user.
    * ``"not_found"`` — no Django user matches ``target_username``.
    * ``"taken"`` — the target user is already linked to a different chat.
    * ``"ok"`` — fresh ``TelegramProfile`` created/refreshed; payload is the
      profile instance with a current ``confirm_token``.
    """
    from django.contrib.auth import get_user_model

    from core.models import TelegramProfile

    User = get_user_model()

    existing = TelegramProfile.objects.filter(chat_id=chat_id).first()
    user = User.objects.filter(username__iexact=target_username).first()
    if not user:
        return "not_found", None
    if existing and existing.user_id != user.id:
        return "already_linked", existing

    other = TelegramProfile.objects.filter(user=user).exclude(chat_id=chat_id).first()
    if other:
        return "taken", other

    profile, _ = TelegramProfile.objects.update_or_create(
        user=user,
        defaults={
            "chat_id": chat_id,
            "username": tg_username,
            "is_confirmed": False,
        },
    )
    return "ok", profile


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if message.chat is None:
        return
    profile = await _ensure_profile(message.chat.id, message.from_user.username or "")
    if profile is None:
        await message.answer(
            "👋 Привет! Я бот KinNet — семейного органайзера.\n\n"
            "Чтобы привязать аккаунт, отправьте команду\n"
            "<code>/link ваш_логин_на_сайте</code>\n"
            "и затем перейдите по ссылке для подтверждения.\n\n"
            f"Если ещё не зарегистрированы — заходите на {_site_url()}/profile/.",
        )
        return

    if not profile.is_confirmed:
        link = f"{_site_url()}/telegram/confirm/{profile.confirm_token}/"
        await message.answer(
            "Аккаунт найден, осталось подтвердить привязку:\n" f"{link}",
        )
        return

    name = profile.user.get_full_name() or profile.user.username
    await message.answer(
        f"С возвращением, {tg_escape(name)}! Используйте меню ниже:",
        reply_markup=main_menu(),
    )


@router.message(Command("link"))
async def on_link(message: Message) -> None:
    if message.chat is None or message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Использование: <code>/link ваш_логин_на_сайте</code>",
        )
        return
    target = parts[1].strip()
    status, payload = await _link_account(
        message.chat.id, message.from_user.username or "", target
    )
    if status == "not_found":
        await message.answer(
            f"Пользователь с логином <b>{tg_escape(target)}</b> не найден на сайте."
        )
        return
    if status == "already_linked":
        await message.answer(
            "Этот чат уже привязан к другому аккаунту. Сначала отвяжите его в профиле."
        )
        return
    if status == "taken":
        await message.answer(
            "Этот аккаунт уже привязан к другому Telegram-чату."
        )
        return
    confirm_url = f"{_site_url()}/telegram/confirm/{payload.confirm_token}/"
    await message.answer(
        "Готово! Войдите на сайт под этим логином и подтвердите привязку:\n"
        f"{confirm_url}"
    )


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(
        "<b>Команды KinNet:</b>\n"
        "/start — приветствие и проверка привязки\n"
        "/link &lt;логин&gt; — привязать Telegram к аккаунту KinNet\n"
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
