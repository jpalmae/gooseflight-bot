"""GooseFlight Bot — Free text handler: sends prompt to Goose and streams response."""

from __future__ import annotations

import asyncio
import time

from aiogram import Router, F
from aiogram.types import Message

from app.config import settings
from app.logging_config import get_logger
from app.services.goose_client import GooseClient
from app.services.session_manager import SessionManager
from app.services.stream_renderer import StreamRenderer
from app.utils.markdown import markdown_to_tg_html, split_message

logger = get_logger(__name__)

router = Router()


@router.message(F.text, ~F.text.startswith("/"))
async def handle_text(
    message: Message,
    goose: GooseClient,
    session_mgr: SessionManager,
) -> None:
    prompt = message.text
    if not prompt or not prompt.strip():
        return

    chat_id = message.chat.id
    session_name = session_mgr.session_name(chat_id)
    is_resume = session_mgr.has_session(chat_id)

    placeholder = await message.answer("⏳ pensando...")

    renderer = StreamRenderer(
        bot=message.bot,
        chat_id=chat_id,
        message_id=placeholder.message_id,
    )

    start_time = time.monotonic()
    full_text = ""  # accumulated text content
    got_response = False

    try:
        async for event in goose.send_prompt(
            message=prompt,
            session_name=session_name,
            resume=is_resume,
        ):
            event_type = event.get("type", "")

            if event_type == "message":
                msg = event.get("message", {})
                content_blocks = msg.get("content", [])

                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")

                    if block_type == "text":
                        # Incremental token — append
                        token = block.get("text", "")
                        full_text += token
                        got_response = True
                        await renderer.update(full_text)

                    elif block_type == "thinking":
                        # Thinking tokens — skip for display
                        pass

            elif event_type == "complete":
                await renderer.finalize()
                break

            elif event_type == "error":
                err = event.get("error", "Error desconocido")
                await renderer.finalize()
                await message.answer(f"❌ {err}")
                break

    except asyncio.CancelledError:
        await renderer.finalize()
        return
    except Exception as e:
        logger.error("stream_error", error=str(e), session_name=session_name)
        await renderer.finalize()
        await message.answer(f"❌ Error: {e}")
        return

    if got_response:
        session_mgr.mark_created(chat_id)

    # Final message with HTML rendering
    if full_text.strip():
        html = markdown_to_tg_html(full_text)
        chunks = split_message(html, max_len=4000)
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=placeholder.message_id,
                text=chunks[0],
                parse_mode="HTML",
            )
        except Exception:
            pass
        for chunk in chunks[1:]:
            try:
                await message.answer(chunk, parse_mode="HTML")
            except Exception:
                await message.answer(chunk)

    elapsed = time.monotonic() - start_time
    if elapsed > settings.completion_notif_threshold_seconds:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        dur = f"{mins}m {secs}s" if mins else f"{secs}s"
        await message.answer(f"✅ Listo en {dur}")
