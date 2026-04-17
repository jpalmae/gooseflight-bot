"""GooseFlight Bot — SQLAlchemy async engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.resolved_sqlite_path}",
    echo=False,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
