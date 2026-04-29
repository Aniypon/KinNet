"""Reply keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/today"), KeyboardButton(text="/events")],
            [KeyboardButton(text="/tasks"), KeyboardButton(text="/messages")],
            [KeyboardButton(text="/families"), KeyboardButton(text="/help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
