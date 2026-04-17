"""GooseFlight Bot — Markdown to Telegram HTML conversion + message splitting.

Uses mistune for robust parsing (handles nested structures, tables, etc.)
then renders to Telegram-compatible HTML subset.
"""

from __future__ import annotations

import html
from typing import Any

import mistune


# ── Telegram HTML renderer ──────────────────────────────────────


class TelegramRenderer(mistune.BaseRenderer):
    """Render mistune AST to Telegram-compatible HTML.

    All methods receive (self, token, state).
    Token is a dict with "type", "children", "text", "attrs", etc.
    """

    NAME = "html"

    def _children(self, token: dict, state: Any) -> str:
        return "".join(
            self.render_token(c, state) for c in token.get("children", [])
        )

    def _get_depth(self, token: dict, state: Any) -> int:
        """Get list nesting depth from parent list's attrs."""
        return token.get("attrs", {}).get("depth", 0)

    # ── Block elements ───────────────────────────────────

    def paragraph(self, token: dict, state: Any) -> str:
        return f"{self._children(token, state)}\n"

    def heading(self, token: dict, state: Any) -> str:
        return f"<b>{self._children(token, state)}</b>\n"

    def blank_line(self, token: dict, state: Any) -> str:
        return ""

    def thematic_break(self, token: dict, state: Any) -> str:
        return "─" * 20 + "\n"

    def block_code(self, token: dict, state: Any) -> str:
        code = token.get("raw", token.get("text", ""))
        info = token.get("attrs", {}).get("info")
        escaped = html.escape(code)
        if info:
            return f'<pre><code class="language-{html.escape(info)}">{escaped}</code></pre>\n'
        return f"<pre>{escaped}</pre>\n"

    def block_quote(self, token: dict, state: Any) -> str:
        text = self._children(token, state).rstrip("\n")
        return f"<blockquote>{text}</blockquote>\n"

    def block_html(self, token: dict, state: Any) -> str:
        return token.get("text", "")

    def block_text(self, token: dict, state: Any) -> str:
        return self._children(token, state)

    def block_error(self, token: dict, state: Any) -> str:
        return self._children(token, state)

    # ── List elements ────────────────────────────────────

    def list(self, token: dict, state: Any) -> str:
        depth = token.get("attrs", {}).get("depth", 0)
        stack = state.env.setdefault("_list_depth_stack", [])
        stack.append(depth)
        result = self._children(token, state)
        stack.pop()
        return result

    def list_item(self, token: dict, state: Any) -> str:
        # Separate block_text from sub-lists for proper formatting
        text_parts = []
        list_parts = []
        for child in token.get("children", []):
            if child.get("type") == "list":
                list_parts.append(self.render_token(child, state))
            else:
                text_parts.append(self.render_token(child, state))

        text = "".join(text_parts).rstrip("\n")
        lists = "".join(list_parts)

        stack = state.env.get("_list_depth_stack", [0])
        depth = stack[-1] if stack else 0
        indent = "  " * depth

        result = f"{indent}  • {text}\n"
        if lists:
            result += lists
        return result

    # ── Inline elements ──────────────────────────────────

    def text(self, token: dict, state: Any) -> str:
        raw = token.get("raw", token.get("text", ""))
        return html.escape(raw)

    def emphasis(self, token: dict, state: Any) -> str:
        return f"<i>{self._children(token, state)}</i>"

    def strong(self, token: dict, state: Any) -> str:
        return f"<b>{self._children(token, state)}</b>"

    def strikethrough(self, token: dict, state: Any) -> str:
        return f"<s>{self._children(token, state)}</s>"

    def link(self, token: dict, state: Any) -> str:
        url = token.get("attrs", {}).get("url", "")
        return f'<a href="{html.escape(url)}">{self._children(token, state)}</a>'

    def image(self, token: dict, state: Any) -> str:
        url = token.get("attrs", {}).get("url", "")
        alt = token.get("attrs", {}).get("alt", "")
        body = self._children(token, state) if token.get("children") else html.escape(alt)
        return f'<a href="{html.escape(url)}">🖼 {body}</a>'

    def inline_code(self, token: dict, state: Any) -> str:
        raw = token.get("text", token.get("raw", ""))
        if not raw and token.get("children"):
            raw = "".join(c.get("text", c.get("raw", "")) for c in token["children"])
        return f"<code>{html.escape(raw)}</code>"

    def codespan(self, token: dict, state: Any) -> str:
        raw = token.get("raw", token.get("text", ""))
        return f"<code>{html.escape(raw)}</code>"

    def linebreak(self, token: dict, state: Any) -> str:
        return "\n"

    def softbreak(self, token: dict, state: Any) -> str:
        return " "

    def inline_html(self, token: dict, state: Any) -> str:
        return token.get("text", "")

    # ── Table elements (same signature: self, token, state) ──

    def table(self, token: dict, state: Any) -> str:
        text = self._children(token, state)
        return f"<pre>{text}</pre>\n"

    def table_head(self, token: dict, state: Any) -> str:
        return self._children(token, state)

    def table_body(self, token: dict, state: Any) -> str:
        return f"{'─' * 40}\n{self._children(token, state)}"

    def table_row(self, token: dict, state: Any) -> str:
        text = self._children(token, state).rstrip(" |")
        return f"{text}\n"

    def table_cell(self, token: dict, state: Any) -> str:
        text = self._children(token, state)
        attrs = token.get("attrs", {})
        head = attrs.get("head", False)
        if head:
            return f"<b>{text}</b> | "
        return f"{text} | "


# ── Public API ──────────────────────────────────────────────────

_md = mistune.create_markdown(
    renderer=TelegramRenderer(),
    plugins=["table", "strikethrough"],
)


def markdown_to_tg_html(md: str) -> str:
    """Convert Markdown (from Goose) to Telegram-compatible HTML."""
    if not md:
        return ""
    return _md(md).strip()


def split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split text into chunks ≤ max_len, respecting paragraph boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_len:
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = remaining.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len

        before = remaining[:cut]
        tick_count = before.count("```")
        if tick_count % 2 == 1:
            last_open = before.rfind("```")
            if last_open > 0:
                cut = last_open

        chunks.append(remaining[:cut])
        remaining = remaining[cut:]

    if remaining:
        chunks.append(remaining)

    return chunks
