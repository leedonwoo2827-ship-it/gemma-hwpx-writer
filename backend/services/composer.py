from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncIterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hwp_mcp.hwpx_vision.lib.vision_prompt import COMPOSER_SYSTEM, composer_user_prompt

from .llm import get_provider


MAX_CONTEXT_CHARS = 60_000


def _truncate(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    half = budget // 2
    return text[:half] + "\n\n... [중략] ...\n\n" + text[-half:]


async def compose_report(plan_md: str, workplan_md: str, wrapup_md: str) -> AsyncIterator[str]:
    per = MAX_CONTEXT_CHARS // 3
    prompt = composer_user_prompt(
        _truncate(plan_md, per),
        _truncate(workplan_md, per),
        _truncate(wrapup_md, per),
    )
    provider = get_provider()
    async for chunk in provider.generate_text(prompt, system=COMPOSER_SYSTEM):
        yield chunk
