"""GooseFlight Bot — Session repository (SQLite async)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.engine import async_session
from app.db.models import BotState, Session
from app.logging_config import get_logger

logger = get_logger(__name__)


class SessionRepo:
    """Manages Goose sessions and bot state in SQLite."""

    # ── Bot state (active session, etc.) ──────────────────

    async def get_active_session_id(self) -> str | None:
        async with async_session() as db:
            r = await db.execute(
                select(BotState).where(BotState.key == "active_session_id")
            )
            row = r.scalar_one_or_none()
            return row.value if row else None

    async def set_active_session_id(self, session_id: str) -> None:
        async with async_session() as db:
            r = await db.execute(
                select(BotState).where(BotState.key == "active_session_id")
            )
            row = r.scalar_one_or_none()
            if row:
                row.value = session_id
                row.updated_at = datetime.now(timezone.utc)
            else:
                db.add(BotState(key="active_session_id", value=session_id))
            await db.commit()

    # ── Session CRUD ──────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        title: str,
        working_directory: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> Session:
        async with async_session() as db:
            r = await db.execute(select(Session).where(Session.id == session_id))
            existing = r.scalar_one_or_none()
            if existing:
                existing.title = title
                existing.last_activity = datetime.now(timezone.utc)
                if working_directory:
                    existing.working_directory = working_directory
                if provider:
                    existing.provider = provider
                if model:
                    existing.model = model
                await db.commit()
                return existing
            s = Session(
                id=session_id,
                title=title,
                working_directory=working_directory,
                provider=provider,
                model=model,
            )
            db.add(s)
            await db.commit()
            return s

    async def list_sessions(self, include_archived: bool = False) -> list[Session]:
        async with async_session() as db:
            stmt = select(Session).order_by(Session.last_activity.desc())
            if not include_archived:
                stmt = stmt.where(Session.is_archived == False)  # noqa: E712
            r = await db.execute(stmt)
            return list(r.scalars().all())

    async def get_session(self, session_id: str) -> Session | None:
        async with async_session() as db:
            r = await db.execute(select(Session).where(Session.id == session_id))
            return r.scalar_one_or_none()

    async def rename_session(self, session_id: str, new_title: str) -> bool:
        async with async_session() as db:
            r = await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(title=new_title)
            )
            await db.commit()
            return r.rowcount > 0

    async def archive_session(self, session_id: str) -> bool:
        async with async_session() as db:
            r = await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(is_archived=True)
            )
            await db.commit()
            return r.rowcount > 0

    async def delete_session(self, session_id: str) -> bool:
        async with async_session() as db:
            s = await db.get(Session, session_id)
            if not s:
                return False
            await db.delete(s)
            await db.commit()
            return True

    async def increment_message_count(self, session_id: str) -> None:
        async with async_session() as db:
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(
                    message_count=Session.message_count + 1,
                    last_activity=datetime.now(timezone.utc),
                )
            )
            await db.commit()


# Singleton
session_repo = SessionRepo()
