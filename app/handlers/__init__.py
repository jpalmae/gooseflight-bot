"""GooseFlight Bot — Handler aggregator."""

from aiogram import Router

from app.handlers.commands import router as commands_router
from app.handlers.execution import router as execution_router
from app.handlers.messages import router as messages_router
from app.handlers.sessions import router as sessions_router


def build_router() -> Router:
    """Combine all handler routers into one."""
    root = Router()
    root.include_router(commands_router)
    root.include_router(sessions_router)
    root.include_router(execution_router)
    root.include_router(messages_router)
    return root
