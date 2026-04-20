from __future__ import annotations

from typing import AsyncIterator

from .llm import get_provider


SECTION_SYSTEM = """당신은 KOICA/ODA 결과보고서 작성 전문가입니다.
주어진 3개 원문(계획서, Work Plan, Wrap Up)에서 특정 섹션의 본문만 한국어로 작성합니다.

규칙:
1. 공공문서 톤 (객관적, 경어)
2. 섹션 제목 자체는 쓰지 말고, 본문만 작성
3. 실제 원문 내용을 근거로만 작성. 없으면 "관련 내용 확인 필요"라고 명시
4. 불릿이 필요하면 "○ ...", 하위는 "- ..." 형식 (Markdown ### 등 사용 금지)
5. 분량은 섹션 성격에 맞게: 개요는 3-5줄, 내용 섹션은 1-2문단
6. 날짜, 숫자, 고유명사는 원문 그대로 사용"""


def _trim(text: str, max_chars: int = 15000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... [중략] ...\n" + text[-half:]


def build_prompt(section_title: str, plan_md: str, workplan_md: str, wrapup_md: str) -> str:
    return f"""다음은 섹션 "{section_title}" 의 본문만 작성하는 작업입니다.

아래 3개 원문을 근거로 해당 섹션에 들어갈 내용을 작성하세요.

<계획서>
{_trim(plan_md)}
</계획서>

<Work Plan>
{_trim(workplan_md)}
</Work Plan>

<Wrap Up>
{_trim(wrapup_md)}
</Wrap Up>

섹션 "{section_title}" 본문(제목 제외, 불릿 기호 ○/- 허용):"""


async def compose_section(
    section_title: str,
    plan_md: str,
    workplan_md: str,
    wrapup_md: str,
) -> str:
    provider = get_provider()
    out_parts: list[str] = []
    prompt = build_prompt(section_title, plan_md, workplan_md, wrapup_md)
    async for chunk in provider.generate_text(prompt, system=SECTION_SYSTEM):
        out_parts.append(chunk)
    return "".join(out_parts).strip()


async def compose_sections_stream(
    section_titles: list[str],
    plan_md: str,
    workplan_md: str,
    wrapup_md: str,
) -> AsyncIterator[tuple[str, str]]:
    """각 섹션별로 순차 생성하며 (section_title, body_text) 튜플을 yield."""
    for title in section_titles:
        body = await compose_section(title, plan_md, workplan_md, wrapup_md)
        yield title, body
