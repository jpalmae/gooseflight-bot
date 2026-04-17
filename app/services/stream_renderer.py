"""GooseFlight Bot — StreamRenderer: progressive message editing with debounce."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

from app.logging_config import get_logger
from app.utils.markdown import markdown_to_tg_html, split_message

logger = get_logger(__name__)


@dataclass
class StreamRenderer:
    """Accumulates text and edits a Telegram message progressively."""

    bot: Bot
    chat_id: int
    message_id: int
    last_text: str = ""
    last_edit: float = 0.0
    min_edit_interval: float = 1.5
    max_length: int = 4000
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _finalized: bool = False

    async def update(self, text: str) -> None:
        """Update with full accumulated text so far."""
        async with self._lock:
            if self._finalized:
                return
            self.last_text = text

            if len(text) > self.max_length:
                await self._finalize_and_split()
                return

            now = time.monotonic()
            if now - self.last_edit < self.min_edit_interval:
                return

            await self._do_edit()

    async def finalize(self) -> None:
        """Final edit when stream completes."""
        async with self._lock:
            if self._finalized:
                return
            self._finalized = True
            await self._do_edit()

    async def _do_edit(self) -> None:
        formatted = markdown_to_tg_html(self.last_text)
        # Truncate for safety
        if len(formatted) > 4090:
            formatted = formatted[:4085] + "\n..."
        try:
            await self.bot.edit_message_text(
                text=formatted,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode="HTML",
            )
            self.last_edit = time.monotonic()
        except TelegramRetryAfter as e:
            logger.warning("rate_limit_edit", retry_after=e.retry_after)
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            err_str = str(e)
            if "not modified" not in err_str.lower():
                logger.debug("edit_failed", error=err_str)

    async def _finalize_and_split(self) -> None:
        """Buffer exceeded max — finalize current message and start new one."""
        await self._do_edit()

        chunks = split_message(self.last_text, max_len=self.max_length)
        remainder = self.last_text
        if len(chunks) > 1:
            remainder = self.last_text[len(chunks[0]):]
        else:
            remainder = ""

        new_msg = await self.bot.send_message(
            chat_id=self.chat_id,
            text="...(continuación)",
            parse_mode="HTML",
        )
        self.message_id = new_msg.message_id
        self.last_text = remainder
        self.last_edit = time.monotonic()
