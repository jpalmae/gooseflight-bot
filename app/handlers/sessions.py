"""GooseFlight Bot — Session commands: /new, /current."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.goose_client import GooseClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("new"))
async def cmd_new(
    message: Message,
    goose: GooseClient,
    session_mgr: SessionManager,
) -> None:
    await session_mgr.close(message.chat.id)
    name = session_mgr.session_name(message.chat.id)
    await message.answer(
        f"✅ Nueva sesión lista.\n<code>{name}</code>",
        parse_mode="HTML",
    )


@router.message(Command("current"))
async def cmd_current(
    message: Message,
    session_mgr: SessionManager,
) -> None:
    name = session_mgr.session_name(message.chat.id)
    active = session_mgr.has_session(message.chat.id)
    if not active:
        await message.answer("📋 Sin sesión activa. Envía un mensaje para crear una.")
        return
    await message.answer(f"🟢 Sesión: <code>{name}</code>", parse_mode="HTML")
