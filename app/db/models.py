"""GooseFlight Bot — SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Sessions ──────────────────────────────────────────────


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    working_directory = Column(String)
    provider = Column(String)
    model = Column(String)
    is_archived = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    last_activity = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Bot state (key-value) ────────────────────────────────


class BotState(Base):
    __tablename__ = "bot_state"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Message log ──────────────────────────────────────────


class MessageLog(Base):
    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    telegram_message_id = Column(Integer)
    role = Column(String(20), nullable=False)  # user | assistant | tool | system
    content = Column(Text, nullable=False)
    tool_call_id = Column(String)
    timestamp = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_messages_session", "session_id", "timestamp"),
    )


# ── Tool approvals ───────────────────────────────────────


class ToolApproval(Base):
    __tablename__ = "tool_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    tool_input = Column(Text, nullable=False)  # JSON
    action = Column(String(30), nullable=False)  # approve | reject | timeout | auto_safe | auto_scoped | auto_full | auto_yolo
    approval_source = Column(String(20), default="manual")  # manual | auto_safe | ...
    dangerous = Column(Boolean, default=False)
    decided_at = Column(DateTime, default=_utcnow)


# ── Pending approvals ────────────────────────────────────


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    request_id = Column(String, primary_key=True)
    chat_id = Column(Integer, nullable=False)
    message_id = Column(Integer, nullable=False)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    tool_data = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)


# ── Autonomy state ───────────────────────────────────────


class SessionAutonomy(Base):
    __tablename__ = "session_autonomy"

    session_id = Column(String, ForeignKey("sessions.id"), primary_key=True)
    mode = Column(String(10), nullable=False, default="manual")  # manual | safe | scoped | full | yolo
    scope_path = Column(String)
    expires_at = Column(DateTime)
    budget_tokens = Column(Integer)
    budget_usd_cents = Column(Integer)
    consumed_tokens = Column(Integer, default=0)
    consumed_usd_cents = Column(Integer, default=0)
    activated_at = Column(DateTime, default=_utcnow)
    activated_with_confirmation = Column(Boolean, default=False)


class AutonomyModeChange(Base):
    __tablename__ = "autonomy_mode_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    from_mode = Column(String(10))
    to_mode = Column(String(10), nullable=False)
    reason = Column(String(50))  # user_command | budget_exceeded | timeout | auto_revert | restart
    changed_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_mode_changes_session", "session_id", "changed_at"),
    )


# ── Command log ──────────────────────────────────────────


class CommandLog(Base):
    __tablename__ = "command_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String, nullable=False)
    args = Column(Text)
    success = Column(Boolean, nullable=False)
    error = Column(Text)
    executed_at = Column(DateTime, default=_utcnow)


# ── File uploads ─────────────────────────────────────────


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    telegram_file_id = Column(String)
    filename = Column(String, nullable=False)
    mime_type = Column(String)
    size_bytes = Column(Integer)
    processing_mode = Column(String(20))  # inline_text | image | workspace
    uploaded_at = Column(DateTime, default=_utcnow)
