"""GooseFlight Bot — /start, /help, /status commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.goose_client import GooseClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, goose: GooseClient, session_mgr: SessionManager) -> None:
    try:
        health = await goose.health()
        status = f"🟢 {health}"
    except Exception:
        status = "🔴 sin conexión"

    text = (
        "<b>🪿 GooseFlight Bot</b>\n"
        "\n"
        f"{status}\n"
        "\n"
        "Envía texto para chatear con Goose.\n"
        "Comandos:\n"
        "  /new — nueva sesión\n"
        "  /current — sesión activa\n"
        "  /stop — detener\n"
        "  /help — manual\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "<b>📖 GooseFlight Manual</b>\n"
        "\n"
        "Envía cualquier texto para chatear con Goose.\n"
        "Goose tiene acceso a herramientas: shell, archivos, etc.\n"
        "\n"
        "<b>Sesiones:</b>\n"
        "  /new — crear nueva sesión\n"
        "  /current — sesión activa\n"
        "\n"
        "<b>Ejecución:</b>\n"
        "  /stop — detener respuesta\n"
        "\n"
        "<b>Sistema:</b>\n"
        "  /status — estado\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message, goose: GooseClient, session_mgr: SessionManager) -> None:
    lines = ["<b>📊 Estado</b>\n"]

    try:
        health = await goose.health()
        lines.append(f"🟢 {health}")
    except Exception as e:
        lines.append(f"🔴 error: {e}")

    session_name = session_mgr.session_name(message.chat.id)
    if session_mgr.has_session(message.chat.id):
        lines.append(f"💬 sesión: <code>{session_name}</code>")
    else:
        lines.append("💬 sesión: ninguna")

    await message.answer("\n".join(lines), parse_mode="HTML")
