"""
PPTX 슬라이드 글쓰기 어시스턴트.

MD 를 양식 PPTX 의 구조(슬라이드 수, 표 슬롯 개수·행/열, 본문 shape 용량 등)에
맞게 재구조화해 **변환 전** 오버플로우·클리핑을 예방하는 LLM 단계.

입력: 원본 MD 경로 + 양식 PPTX 경로
출력: 재구조화된 MD 스트리밍 (SSE)

변환 후 감지되는 문제(pptx_md_refiner)와 달리, 이 단계는 "문제 발생 전" 에
structure-aware 프롬프트로 한 번에 맞춰준다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.llm import get_provider
from doc_mcp.md2pptx.pack import unpack
from doc_mcp.md2pptx.slide_scanner import scan_unpacked, SlotCatalog


SLIDE_COMPOSER_SYSTEM = """당신은 PPTX 슬라이드용 Markdown 재구조화 전문가입니다.
원본 MD 와 "대상 양식 PPTX 의 구조 정보" 를 받아, 슬라이드 변환 시
오버플로우·클리핑 없이 깔끔하게 들어가도록 MD 를 재구조화합니다.

규칙:
1. 원본의 어투·단어·숫자·고유명사를 **최대한 보존**. 구조만 재배열.
2. 각 `## H2` = 한 슬라이드. 양식의 slide 용량(섹션 디바이더 + 표·본문 shape)과
   MD H2 개수를 맞춤. MD H2 가 양식보다 많으면 유사 섹션끼리 병합,
   적으면 긴 섹션을 `## X-1`, `## X-2` 로 분할.
3. **표** 는 양식 표 슬롯의 `행수` 초과 시 분할:
   - 예) 양식 표 슬롯 = 5행 / MD 표 = 12행 → 2~3개 표로 나누고 각각 별개 H2 섹션으로.
   - 표 헤더는 양식 헤더와 유사하게 맞춤 (가능한 범위 내).
4. **줄글** 은 양식의 body shape 용량에 맞춰:
   - 긴 줄글 (100자↑) → 핵심 bullet 3~5개로 요약 (명사구 위주).
   - 이미 bullet 이면 개수만 조정.
5. **빈 자리 창작 금지** — 원본 MD 에 근거 없는 내용 추가 금지. 필요하면 `[TBD]` 표시.
6. 출력은 **완성된 MD 전문** 1개. 코드펜스·설명·메타코멘트 금지. MD 본문만.
"""


def _describe_template_structure(catalog: SlotCatalog) -> str:
    """양식 PPTX 를 LLM 이 이해할 수 있는 구조 요약 텍스트로 변환."""
    lines: list[str] = []
    total_slides = len(catalog.slide_trees)
    lines.append(f"- 총 슬라이드 수: {total_slides}장")

    # 표 슬롯
    if catalog.table_slots:
        lines.append(f"- 표 슬롯: {len(catalog.table_slots)}개")
        for i, t in enumerate(catalog.table_slots, start=1):
            hdr_preview = " | ".join(h[:20] for h in t.headers if h)[:80]
            lines.append(
                f"  · 표 {i} (슬라이드 {t.slide_idx}): {t.n_rows}행 × {t.n_cols}열"
                + (f", 헤더: {hdr_preview}" if hdr_preview else "")
            )
    else:
        lines.append("- 표 슬롯: 없음")

    # 텍스트 shape 을 용도별로 분류 (휴리스틱)
    short_slots = [s for s in catalog.text_slots if len(s.text) <= 30]
    body_slots = [s for s in catalog.text_slots if len(s.text) > 30]

    lines.append(f"- 짧은 텍스트 slot (제목·레이블 추정): {len(short_slots)}개")
    if body_slots:
        lines.append(f"- 본문 텍스트 slot (줄글·bullet 용, 기존 텍스트 30자↑): {len(body_slots)}개")
        for i, s in enumerate(body_slots[:5], start=1):
            preview = s.text[:60].replace("\n", " ")
            lines.append(f"  · 본문 {i} (슬라이드 {s.slide_idx}): 기존 ~{len(s.text)}자 \"{preview}...\"")
    else:
        lines.append("- 본문 텍스트 slot: **없음** (줄글 주입 불가 → 짧게 요약 필수)")

    # 슬라이드별 역할 요약
    slide_roles: dict[int, list[str]] = {}
    for t in catalog.table_slots:
        slide_roles.setdefault(t.slide_idx, []).append("표")
    for s in body_slots:
        slide_roles.setdefault(s.slide_idx, []).append("본문")
    for s in short_slots:
        slide_roles.setdefault(s.slide_idx, []).append("제목")

    lines.append("- 슬라이드별 구성:")
    for idx in sorted(slide_roles.keys()):
        roles = slide_roles[idx]
        # "제목" 만 있는 슬라이드 = section-divider 후보
        if roles == ["제목"] or (len(roles) == 1 and roles[0] == "제목"):
            lines.append(f"  · 슬라이드 {idx}: 섹션 디바이더 (짧은 제목만)")
        else:
            unique = sorted(set(roles), key=roles.index)
            count = {r: roles.count(r) for r in unique}
            desc = ", ".join(f"{r}×{count[r]}" if count[r] > 1 else r for r in unique)
            lines.append(f"  · 슬라이드 {idx}: {desc}")

    return "\n".join(lines)


def _user_prompt(md_text: str, template_desc: str, user_hint: str | None) -> str:
    parts: list[str] = []
    parts.append("## 대상 양식 PPTX 구조")
    parts.append(template_desc)
    parts.append("")

    if user_hint and user_hint.strip():
        parts.append("## 사용자 추가 지시")
        parts.append(user_hint.strip())
        parts.append("")

    parts.append("## 원본 MD")
    parts.append("```markdown")
    parts.append(md_text)
    parts.append("```")
    parts.append("")
    parts.append(
        "위 양식 구조에 맞게 **재구조화된 MD 전문** 을 출력하세요. "
        "원본 내용·어투 보존, 슬라이드 수와 표/본문 용량에 맞춰 분할·요약. "
        "코드펜스·설명 금지, MD 본문만."
    )
    return "\n".join(parts)


def _strip_fences(text: str) -> str:
    import re
    s = text.strip()
    s = re.sub(r"^```(?:markdown|md)?\s*\n", "", s)
    s = re.sub(r"\n```\s*$", "", s)
    return s


def _scan_template(template_pptx: str) -> str:
    """양식 PPTX 를 임시 디렉토리에 언팩하고 구조 요약 텍스트를 반환."""
    with tempfile.TemporaryDirectory(prefix="slide_composer_") as tmp:
        unpacked = unpack(Path(template_pptx), Path(tmp) / "unpacked")
        catalog = scan_unpacked(unpacked)
        return _describe_template_structure(catalog)


async def draft_slide_md(
    md_path: str,
    template_pptx: str,
    user_hint: str | None = None,
) -> AsyncIterator[str]:
    """양식 PPTX 구조를 반영해 MD 를 재구조화 스트리밍."""
    md_text = Path(md_path).read_text(encoding="utf-8", errors="replace")
    template_desc = _scan_template(template_pptx)
    prompt = _user_prompt(md_text, template_desc, user_hint)
    provider = get_provider()
    async for chunk in provider.generate_text(prompt, system=SLIDE_COMPOSER_SYSTEM):
        yield chunk


def short_stem(stem: str, n: int = 3) -> str:
    """파일명 길이 폭주 방지: 입력 stem 의 앞 n 자만 사용. 공백·구분자는 그대로 둠.
    예: '0.출장일정-오른-진짜_suggested_20260424_112254' → '0.출' (n=3)
    """
    s = stem.strip()
    return s[:n] if len(s) > n else s


def save_slide_md(md_path: str, drafted_text: str) -> str:
    """LLM 이 뱉은 MD 를 `{앞3자}_sl_{ts}.md` 로 같은 폴더에 저장 (ts: yymmdd_HHMMSS)."""
    import time as _time
    p = Path(md_path)
    ts = _time.strftime("%y%m%d_%H%M%S")
    out = p.with_name(f"{short_stem(p.stem)}_sl_{ts}.md")
    cleaned = _strip_fences(drafted_text)
    out.write_text(cleaned, encoding="utf-8")
    return str(out)
