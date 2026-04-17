"""GooseFlight Bot — /stop command."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.goose_client import GooseClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("stop"))
async def cmd_stop(
    message: Message,
    goose: GooseClient,
    session_mgr: SessionManager,
) -> None:
    session_name = session_mgr.session_name(message.chat.id)
    if not session_mgr.has_session(message.chat.id):
        await message.answer("No hay sesión activa.")
        return
    await goose.stop(session_name)
    await message.answer("⏹ Detenido.")
