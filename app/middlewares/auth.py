"""GooseFlight Bot — Single-user authentication middleware."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from app.logging_config import get_logger

logger = get_logger(__name__)


class SingleUserAuthMiddleware(BaseMiddleware):
    """Rejects every update not coming from the authorized Telegram user ID."""

    def __init__(self, authorized_user_id: int):
        self.authorized_user_id = authorized_user_id
        self._unauthorized_count: int = 0
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id != self.authorized_user_id:
            self._unauthorized_count += 1
            logger.warning(
                "unauthorized_access",
                user_id=user.id if user else None,
                username=user.username if user else None,
                total=self._unauthorized_count,
            )
            return  # silence — no response to unauthorized users
        return await handler(event, data)
