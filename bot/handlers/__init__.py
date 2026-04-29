"""Aggregate router for all bot handlers."""

from __future__ import annotations

from aiogram import Router

from . import auth, core_commands  # noqa: F401

router = Router(name="kinnet-root")
router.include_router(auth.router)
router.include_router(core_commands.router)
