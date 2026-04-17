"""GooseFlight Bot — Database init / table creation."""

from __future__ import annotations

from app.db.engine import engine
from app.db.models import Base


async def init_db() -> None:
    """Create all tables if they don't exist (for dev without Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
