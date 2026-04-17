"""GooseFlight Bot — ACP client for goose serve (JSON-RPC over HTTP/SSE)."""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# ACP JSON-RPC protocol version
ACP_VERSION = "0.1.0"


class ACPSession:
    """Manages a single ACP session with goose serve.

    The ACP protocol requires:
    1. POST /acp with initialize → creates session, returns capabilities
    2. Subsequent POST /acp with acp/prompt → streams response as SSE
    3. Session ID is in Acp-Session-Id header (client-generated UUID)
    4. Each POST creates/uses a session; sessions persist between requests
       as long as the server keeps them (goose serve keeps them alive).

    The session_id is generated client-side and sent via Acp-Session-Id header.
    """

    def __init__(self, client: httpx.AsyncClient, session_id: str):
        self._client = client
        self.session_id = session_id
        self._initialized = False
        self._capabilities: dict = {}

    async def initialize(self) -> dict:
        """Initialize the ACP session. Must be called first."""
        resp = await self._post_jsonrpc("initialize", {
            "protocolVersion": ACP_VERSION,
            "clientInfo": {"name": "gooseflight-bot", "version": "0.1.0"},
        })
        self._capabilities = resp.get("agentCapabilities", {})
        self._initialized = True
        logger.info("acp_initialized", session_id=self.session_id, caps=list(self._capabilities.keys()))
        return resp

    async def prompt(self, message: str) -> AsyncIterator[dict]:
        """Send a prompt and yield SSE events as they arrive."""
        if not self._initialized:
            await self.initialize()

        payload = {
            "jsonrpc": "2.0",
            "method": "acp/prompt",
            "id": self._next_id(),
            "params": {
                "messages": [{"role": "user", "content": message}],
            },
        }

        async with self._client.stream(
            "POST", "/acp", json=payload
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                logger.error("prompt_failed", status=response.status_code, body=body[:200])
                raise RuntimeError(f"ACP prompt failed: {response.status_code}")

            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        event = json.loads(data_str)
                        yield event
                    except json.JSONDecodeError:
                        logger.warning("sse_parse_error", data=data_str[:200])
                elif line.startswith("event:"):
                    pass  # event type, ignore

    async def list_sessions(self) -> list[dict]:
        """List available sessions."""
        resp = await self._post_jsonrpc("session/list", {})
        return resp if isinstance(resp, list) else []

    async def close(self) -> None:
        """Close the session."""
        try:
            await self._post_jsonrpc("session/close", {})
        except Exception:
            pass

    async def _post_jsonrpc(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and parse the SSE response."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._next_id(),
            "params": params,
        }
        r = await self._client.post("/acp", json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"ACP error {r.status_code}: {r.text[:200]}")

        # Parse SSE data line
        for line in r.text.strip().split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "error" in data:
                    raise RuntimeError(f"ACP JSON-RPC error: {data['error']}")
                return data.get("result", {})
        return {}

    _id_counter: int = 0

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter


class GooseACPClient:
    """Factory for ACP sessions against goose serve."""

    def __init__(self) -> None:
        self._base_url = settings.goosed_base_url
        self._sessions: dict[str, ACPSession] = {}

    def _make_client(self, session_id: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Acp-Session-Id": session_id,
            },
            timeout=httpx.Timeout(30.0, read=120.0),
        )

    async def create_session(self) -> ACPSession:
        """Create and initialize a new ACP session."""
        sid = str(uuid.uuid4())
        client = self._make_client(sid)
        session = ACPSession(client, sid)
        await session.initialize()
        self._sessions[sid] = session
        logger.info("session_created", session_id=sid)
        return session

    async def get_session(self, session_id: str) -> ACPSession | None:
        return self._sessions.get(session_id)

    async def close_all(self) -> None:
        for sid, session in list(self._sessions.items()):
            try:
                await session.close()
                await session._client.aclose()
            except Exception:
                pass
        self._sessions.clear()

    async def health(self) -> str:
        """Check goose serve health."""
        async with httpx.AsyncClient(base_url=self._base_url, timeout=5.0) as c:
            r = await c.get("/health")
            return r.text
