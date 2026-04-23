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
from app.utils.markdown import markdown_to_tg_html

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
                        try:
                            await renderer.update(full_text)
                        except Exception as render_err:
                            # Rendering errors should NOT kill the stream
                            logger.warning(
                                "update_error",
                                error=str(render_err),
                                session_name=session_name,
                            )

                    elif block_type == "thinking":
                        # Thinking tokens — skip for display
                        pass

            elif event_type == "complete":
                try:
                    await renderer.finalize()
                except Exception as render_err:
                    logger.warning("finalize_error", error=str(render_err))
                break

            elif event_type == "error":
                err = event.get("error", "Error desconocido")
                try:
                    await renderer.finalize()
                except Exception:
                    pass
                await message.answer(f"❌ {err}")
                break

    except asyncio.CancelledError:
        try:
            await renderer.finalize()
        except Exception:
            pass
        return
    except Exception as e:
        logger.error("stream_error", error=str(e), session_name=session_name)
        try:
            await renderer.finalize()
        except Exception:
            pass
        # Send error to user, but don't show raw Telegram API errors
        err_msg = str(e)
        if "separator" in err_msg.lower() or "chunk" in err_msg.lower():
            await message.answer("⚠️ Mensaje muy largo — parte de la respuesta se perdió. Puedo continuar si me escribes de nuevo.")
        else:
            await message.answer(f"❌ Error: {e}")
        return

    # Safety net: ensure finalize is called (no-op if already called via complete/error)
    if not renderer._finalized:
        try:
            await renderer.finalize()
        except Exception:
            pass

    if got_response:
        session_mgr.mark_created(chat_id)

    elapsed = time.monotonic() - start_time
    if elapsed > settings.completion_notif_threshold_seconds:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        dur = f"{mins}m {secs}s" if mins else f"{secs}s"
        await message.answer(f"✅ Listo en {dur}")
