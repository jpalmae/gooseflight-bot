"""GooseFlight Bot — Goose subprocess client using `goose run`."""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def _read_lines_unlimited(
    stream: asyncio.StreamReader,
) -> AsyncIterator[str]:
    """Read lines from an asyncio StreamReader without the 64KB limit.

    The default ``async for line in stream`` uses ``readline()`` which raises
    ``ValueError: Separator is found, but chunk is longer than limit`` when a
    single line exceeds 64 KiB.  This helper reads chunks manually and yields
    complete lines regardless of size.
    """
    buf = bytearray()
    while True:
        # Read in 64KB chunks (but accumulate without limit)
        chunk = await stream.read(65536)
        if not chunk:
            # EOF — yield any remaining data
            if buf:
                yield buf.decode(errors="replace")
            break
        buf.extend(chunk)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode(errors="replace")


class GooseClient:
    """Interface to Goose via `goose run` subprocess.

    Session management:
    - First message: goose run --name <chat_name> -t "msg" (creates named session)
    - Subsequent:    goose run --name <chat_name> -r -t "msg" (resume named session)
    """

    def __init__(self) -> None:
        self._goose_bin = settings.goose_bin or os.path.expanduser("~/.local/bin/goose")
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._env = self._build_env()

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update({
            "GOOSE_DISABLE_KEYRING": "true",
            "GOOSE_PROVIDER": settings.goose_provider,
            "GOOSE_MODEL": settings.goose_model,
            "AVIAN_API_KEY": settings.avian_api_key,
            "AVIAN_HOST": settings.avian_host,
        })
        return env

    async def send_prompt(
        self,
        message: str,
        session_name: str,
        resume: bool = False,
    ) -> AsyncIterator[dict]:
        """Send a prompt and yield stream-json events.

        Stream format (NDJSON):
        - {"type":"message","message":{"content":[{"type":"text","text":"..."}]}}
        - {"type":"complete","total_tokens":1234}

        Text content is per-token (incremental), NOT accumulated.
        Thinking content has type "thinking" with "thinking" field.

        Args:
            message: The user prompt.
            session_name: Named session identifier (e.g. "tg_123456").
            resume: If True, resume existing session.
        """
        cmd = [
            self._goose_bin, "run",
            "-t", message,
            "-q",
            "--output-format", "stream-json",
            "--name", session_name,
        ]

        if resume:
            cmd.append("-r")

        logger.info("goose_run", session_name=session_name, resume=resume)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )

        self._processes[session_name] = proc

        try:
            async for line in _read_lines_unlimited(proc.stdout):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                    yield event
                except json.JSONDecodeError:
                    logger.warning("parse_error", line=line_str[:200])

            await proc.wait()
            stderr = (await proc.stderr.read()).decode().strip()
            if proc.returncode and proc.returncode != 0:
                logger.error("goose_exit", code=proc.returncode, stderr=stderr[:500])

        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
        finally:
            self._processes.pop(session_name, None)

    async def stop(self, session_name: str) -> None:
        proc = self._processes.pop(session_name, None)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

    async def health(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            self._goose_bin, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode == 0:
            ver = (await proc.stdout.read()).decode().strip()
            return f"goose v{ver}"
        return "goose: not found"
