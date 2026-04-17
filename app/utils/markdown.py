"""GooseFlight Bot — Markdown to Telegram HTML conversion + message splitting."""

from __future__ import annotations

import html
import re


def markdown_to_tg_html(md: str) -> str:
    """Convert Markdown (from Goose) to Telegram-compatible HTML."""
    if not md:
        return ""

    text = md

    # Fenced code blocks (must be first — they protect content inside)
    def _code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = html.escape(m.group(2))
        if lang:
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        return f"<pre>{code}</pre>"

    text = re.sub(r"```(\w*)\n(.*?)```", _code_block, text, flags=re.DOTALL)

    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Bold (**not** inside code)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

    # Italic (single *, not inside bold)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)

    # Strikethrough
    text = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", text)

    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Headers → bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    return text


def split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split text into chunks ≤ max_len, respecting paragraph boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_len:
        # Try to cut at double newline
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = remaining.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len

        # Don't split inside a code block
        before = remaining[:cut]
        tick_count = before.count("```")
        if tick_count % 2 == 1:
            # We're inside a code block — find the opening ```
            last_open = before.rfind("```")
            if last_open > 0:
                cut = last_open

        chunks.append(remaining[:cut])
        remaining = remaining[cut:]

    if remaining:
        chunks.append(remaining)

    return chunks
