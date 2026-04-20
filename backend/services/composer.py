from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncIterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hwp_mcp.hwpx_vision.lib.vision_prompt import (
    COMPOSER_SYSTEM,
    TEMPLATE_COMPOSER_SYSTEM,
    composer_user_prompt,
    template_composer_user_prompt,
)

from .llm import get_provider


MAX_CONTEXT_CHARS = 60_000


def _truncate(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    half = budget // 2
    return text[:half] + "\n\n... [중략] ...\n\n" + text[-half:]


async def compose_report(sources: list[tuple[str, str]]) -> AsyncIterator[str]:
    per = MAX_CONTEXT_CHARS // max(1, len(sources))
    trimmed = [(n, _truncate(c, per)) for n, c in sources]
    prompt = composer_user_prompt(trimmed)
    provider = get_provider()
    async for chunk in provider.generate_text(prompt, system=COMPOSER_SYSTEM):
        yield chunk


async def compose_with_template_headings(
    template_headings: list[dict],
    sources: list[tuple[str, str]],
) -> AsyncIterator[str]:
    per = MAX_CONTEXT_CHARS // max(1, len(sources))
    trimmed = [(n, _truncate(c, per)) for n, c in sources]
    prompt = template_composer_user_prompt(template_headings, trimmed)
    provider = get_provider()
    async for chunk in provider.generate_text(prompt, system=TEMPLATE_COMPOSER_SYSTEM):
        yield chunk
