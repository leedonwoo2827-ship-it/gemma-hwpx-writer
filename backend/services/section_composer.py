from __future__ import annotations

from typing import AsyncIterator

from .llm import get_provider


SECTION_SYSTEM = """당신은 한국어 공공/행정 결과보고서 작성 전문가입니다.
주어진 여러 원문에서 특정 섹션의 본문만 한국어로 작성합니다.

규칙:
1. 공공문서 톤 (객관적, 경어)
2. 섹션 제목 자체는 쓰지 말고, 본문만 작성
3. 실제 원문 내용을 근거로만 작성. 없으면 "관련 내용 확인 필요"라고 명시
4. 하위 주제가 여러 개면 각각을 `### 제목` 또는 `#### 제목` Markdown 헤딩으로 구분
5. 같은 헤딩 아래 상세 항목은 단일 레벨 불릿 `- 항목명: 내용` 만 사용. 들여쓰기 금지.
6. 분량은 섹션 성격에 맞게: 개요 3-5줄, 내용 섹션 1-2문단
7. 날짜, 숫자, 고유명사는 원문 그대로 사용"""


def _trim(text: str, max_chars: int = 15000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... [중략] ...\n" + text[-half:]


def build_prompt(section_title: str, sources: list[tuple[str, str]]) -> str:
    parts = [f"<{name}>\n{_trim(content)}\n</{name}>" for name, content in sources]
    body = "\n\n".join(parts)
    return f"""다음은 섹션 "{section_title}" 의 본문만 작성하는 작업입니다.

아래 {len(sources)}개 원문을 근거로 해당 섹션에 들어갈 내용을 작성하세요.

{body}

섹션 "{section_title}" 본문(제목 제외, 불릿 기호 ○/- 허용):"""


async def compose_section(
    section_title: str,
    sources: list[tuple[str, str]],
) -> str:
    provider = get_provider()
    out_parts: list[str] = []
    prompt = build_prompt(section_title, sources)
    async for chunk in provider.generate_text(prompt, system=SECTION_SYSTEM):
        out_parts.append(chunk)
    return "".join(out_parts).strip()


async def compose_sections_stream(
    section_titles: list[str],
    sources: list[tuple[str, str]],
) -> AsyncIterator[tuple[str, str]]:
    for title in section_titles:
        body = await compose_section(title, sources)
        yield title, body
