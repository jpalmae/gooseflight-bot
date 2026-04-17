"""GooseFlight Bot — Session manager for goose subprocess sessions."""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Maps Telegram chats to named goose sessions.

    Session names are stable per chat (e.g. "tg_123456").
    Tracks whether a session has been used (needs --resume) or is new.
    """

    def __init__(self) -> None:
        self._has_session: dict[int, bool] = {}  # chat_id -> True if goose session exists

    def session_name(self, chat_id: int) -> str:
        """Generate a stable session name for a Telegram chat."""
        return f"tg_{chat_id}"

    def has_session(self, chat_id: int) -> bool:
        """Check if the chat has an existing goose session (needs resume)."""
        return self._has_session.get(chat_id, False)

    def mark_created(self, chat_id: int) -> None:
        """Mark that a goose session has been created for this chat."""
        self._has_session[chat_id] = True
        logger.info("session_created", chat_id=chat_id)

    async def close(self, chat_id: int) -> None:
        self._has_session.pop(chat_id, None)
