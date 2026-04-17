"""GooseFlight Bot — Configuration via pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(path: Optional[str]) -> Optional[str]:
    """Read a Docker secret file if provided, return None otherwise."""
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return p.read_text().strip()
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_bot_token_file: str = ""
    authorized_user_id: int = 0

    # ── Goose ──────────────────────────────────────────────
    goosed_url: str = "http://localhost:3284"
    goose_secret: str = ""
    goose_secret_file: str = ""
    goose_provider: str = "avian"
    goose_model: str = "glm-5.1"
    avian_api_key: str = ""
    avian_host: str = "https://api.z.ai/api/coding/paas/v4"
    goose_bin: str = ""

    # ── Whisper ───────────────────────────────────────────
    whisper_backend: str = "openai"  # openai | local
    openai_api_key: str = ""
    openai_api_key_file: str = ""
    whisper_local_model: str = "small"
    whisper_language: str = "es"

    # ── Paths ─────────────────────────────────────────────
    data_dir: str = "/data"
    sqlite_path: str = ""  # computed if empty
    workspace_dir: str = "/workspace"

    # ── Behaviour ─────────────────────────────────────────
    stream_edit_interval_seconds: float = 1.5
    completion_notif_threshold_seconds: int = 30
    tool_approval_timeout_seconds: int = 600
    max_file_size_bytes: int = 52_428_800  # 50 MB
    max_inline_text_size_bytes: int = 102_400  # 100 KB

    # ── Logging ───────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json | console
    tz: str = "America/Santiago"

    # ── Autonomy defaults ─────────────────────────────────
    autonomy_scoped_default_timeout_min: int = 60
    autonomy_scoped_max_timeout_min: int = 240
    autonomy_full_default_timeout_min: int = 15
    autonomy_full_max_timeout_min: int = 60
    autonomy_yolo_default_timeout_min: int = 10
    autonomy_yolo_max_timeout_min: int = 10

    autonomy_scoped_default_budget_usd: int = 500  # cents
    autonomy_full_default_budget_usd: int = 1000
    autonomy_yolo_default_budget_usd: int = 2000

    autonomy_loop_window_minutes: int = 5
    autonomy_loop_same_tool_threshold: int = 15
    autonomy_loop_same_input_threshold: int = 5

    autonomy_persist_safe: bool = False

    # ── Resolved properties ───────────────────────────────

    @property
    def resolved_token(self) -> str:
        return _read_secret(self.telegram_bot_token_file) or self.telegram_bot_token

    @property
    def resolved_goose_secret(self) -> str:
        return _read_secret(self.goose_secret_file) or self.goose_secret

    @property
    def resolved_openai_key(self) -> str:
        return _read_secret(self.openai_api_key_file) or self.openai_api_key

    @property
    def resolved_sqlite_path(self) -> str:
        if self.sqlite_path:
            return self.sqlite_path
        return os.path.join(self.data_dir, "bot.sqlite")

    @property
    def goosed_base_url(self) -> str:
        return self.goosed_url.rstrip("/")


settings = Settings()
