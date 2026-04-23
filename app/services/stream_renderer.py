"""GooseFlight Bot — StreamRenderer: progressive message editing with debounce."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

from app.logging_config import get_logger
from app.utils.markdown import markdown_to_tg_html, split_message

logger = get_logger(__name__)

# Telegram message length limit
TG_MAX_LEN = 4096


def _strip_html(html: str) -> str:
    """Remove all HTML tags, returning plain text."""
    return re.sub(r"<[^>]+>", "", html)


def _safe_truncate_html(html: str, max_len: int = 4085) -> str:
    """Truncate HTML text at a safe boundary, closing open tags.

    Returns a string of at most max_len characters.
    """
    if len(html) <= max_len:
        return html

    # Reserve room for closing tags + "\n..." (4 chars)
    # Budget for closing tags: rough estimate 5 chars per open tag × 5 = 25
    budget = max_len - 30

    # Find safe cut point: last '>' or newline before budget
    cut = html.rfind(">", 0, budget)
    if cut == -1 or cut < budget // 2:
        cut = html.rfind("\n", 0, budget)
    if cut == -1 or cut < budget // 2:
        cut = budget

    truncated = html[:cut + 1]

    # Close potentially open tags
    open_tags: list[str] = []
    for match in re.finditer(r"<(/?)(\w+)[^>]*>", truncated):
        is_close = match.group(1) == "/"
        tag = match.group(2).lower()
        if tag in ("br", "hr", "img"):
            continue
        if is_close:
            if open_tags and open_tags[-1] == tag:
                open_tags.pop()
        else:
            open_tags.append(tag)

    # Close remaining open tags in reverse order
    for tag in reversed(open_tags):
        truncated += f"</{tag}>"

    truncated += "\n..."

    # Final safety: if still too long, hard-truncate
    if len(truncated) > max_len:
        truncated = truncated[:max_len - 4] + "\n..."

    return truncated


@dataclass
class StreamRenderer:
    """Accumulates text and edits a Telegram message progressively."""

    bot: Bot
    chat_id: int
    message_id: int
    last_text: str = ""
    last_edit: float = 0.0
    min_edit_interval: float = 10.0
    max_length: int = 3500  # Lower than TG limit to leave room for HTML overhead
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _finalized: bool = False
    _rate_limit_until: float = 0.0
    _rate_limit_hits: int = 0
    _max_rate_limit_retries: int = 3
    _pending_edit: bool = False
    _committed_offset: int = 0  # chars already sent to previous messages

    async def update(self, text: str) -> None:
        """Update with full accumulated text so far."""
        async with self._lock:
            if self._finalized:
                return
            self.last_text = text

            # Only work with the uncommitted portion
            pending = text[self._committed_offset:]
            if len(pending) > self.max_length:
                await self._finalize_and_split()
                return

            now = time.monotonic()
            if now - self.last_edit < self.min_edit_interval:
                return

            # Rate-limited: mark pending so finalize flushes the latest text
            if now < self._rate_limit_until:
                self._pending_edit = True
                return

            self._pending_edit = False
            await self._do_edit()

    async def finalize(self) -> bool:
        """Final edit when stream completes. Returns True if edit succeeded."""
        async with self._lock:
            if self._finalized:
                return True
            self._finalized = True
            # Always attempt the final edit, clear cooldown
            self._rate_limit_until = 0.0
            return await self._do_edit(is_final=True)

    def _pending_text(self) -> str:
        """Return only the uncommitted portion of text."""
        return self.last_text[self._committed_offset:]

    async def _do_edit(self, is_final: bool = False) -> bool:
        """Edit the Telegram message. Returns True on success.

        On HTML parsing errors from Telegram, falls back to plain text.
        """
        raw = self._pending_text()
        if not raw.strip():
            return True

        formatted = markdown_to_tg_html(raw)

        # Smart HTML-aware truncation
        if len(formatted) > TG_MAX_LEN - 6:
            formatted = _safe_truncate_html(formatted, max_len=TG_MAX_LEN - 10)

        for attempt in range(self._max_rate_limit_retries + 1):
            try:
                await self.bot.edit_message_text(
                    text=formatted,
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    parse_mode="HTML",
                )
                self.last_edit = time.monotonic()
                self._rate_limit_hits = 0
                self._pending_edit = False
                return True
            except TelegramRetryAfter as e:
                self._rate_limit_hits += 1

                if is_final and attempt < self._max_rate_limit_retries:
                    # Final edit: retry with capped sleep (max 15s per attempt)
                    sleep = min(e.retry_after, 15)
                    logger.warning(
                        "rate_limit_retry",
                        retry_after=e.retry_after,
                        sleep=sleep,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(sleep)
                    continue

                # Mid-stream or exhausted retries: set cooldown and bail
                cooldown = min(e.retry_after, 30)
                self._rate_limit_until = time.monotonic() + cooldown
                logger.warning(
                    "rate_limit_edit",
                    retry_after=e.retry_after,
                    cooldown=cooldown,
                    hits=self._rate_limit_hits,
                )
                return False
            except Exception as e:
                err_str = str(e)
                if "not modified" in err_str.lower():
                    return True

                # HTML parsing / chunk errors from Telegram — fallback to plain text
                if any(kw in err_str.lower() for kw in ("separator", "chunk", "parse", "entity")):
                    logger.warning("html_fallback_plain", error=err_str)
                    try:
                        plain = _strip_html(formatted)
                        if len(plain) > TG_MAX_LEN - 10:
                            plain = plain[:TG_MAX_LEN - 15] + "\n..."
                        await self.bot.edit_message_text(
                            text=plain,
                            chat_id=self.chat_id,
                            message_id=self.message_id,
                            # No parse_mode — plain text
                        )
                        self.last_edit = time.monotonic()
                        return True
                    except Exception as fallback_err:
                        logger.warning("plain_fallback_failed", error=str(fallback_err))
                        return False

                logger.debug("edit_failed", error=err_str)
                return False

        logger.warning("rate_limit_max_retries_exceeded", hits=self._rate_limit_hits)
        return False

    async def _finalize_and_split(self) -> None:
        """Buffer exceeded max — finalize current message and start new one."""
        # Edit current message (resilient to failures)
        try:
            await self._do_edit()
        except Exception as e:
            logger.warning("split_edit_failed", error=str(e))

        pending = self._pending_text()
        chunks = split_message(pending, max_len=self.max_length)
        if len(chunks) > 1:
            # Commit what we already sent (first chunk)
            self._committed_offset += len(chunks[0])
        else:
            self._committed_offset = len(self.last_text)

        # Send continuation marker as new message
        try:
            new_msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text="...(continuación)",
            )
            self.message_id = new_msg.message_id
        except Exception as e:
            logger.warning("split_send_failed", error=str(e))

        self.last_edit = time.monotonic()
