"""
PPTX 결과 분석 → LLM 이 MD 재작성 제안.

입력:
  - 원본 MD 경로
  - analyzer.analyze_output() 결과 (issues 리스트)
  - 양식 PPTX 경로 (plan_text 생성용)
  - 사용자 자연어 힌트 (옵션)

출력: SSE 로 새 MD 스트리밍 (LLM 응답 그대로, 후처리로 코드펜스 제거).

Provider: Gemini 주력, Ollama 폴백. `backend.services.llm.get_provider()` 재사용.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncIterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.llm import get_provider


REFINER_SYSTEM = """당신은 Markdown 편집 어시스턴트입니다.
원본 MD 와 "MD → PPTX 변환 결과의 문제 리스트" 를 받아, 다음 변환에서
문제가 해결되도록 MD 를 **최소 변경** 으로 수정합니다.

수정 규칙:
1. 원본 MD 의 어투·단어·숫자·고유명사를 **최대한 보존**. 구조만 변경.
2. **표 넘침** (table_overflow): 해당 표를 논리적 단위로 나눠 별개 H2 섹션으로 분할.
   예) `## 2. 활동` 아래 긴 표 → `## 2-1. 활동 (1/2)`, `## 2-2. 활동 (2/2)`.
3. **셀 클리핑** (cell_clip): 긴 셀을 요약하거나, 가능하면 같은 행을 두 행으로 쪼갬.
4. **미매칭 표** (unmatched_table): 헤더를 양식 표 헤더에 맞추도록 rename 또는 열 재배치.
   양식 헤더를 모르면 그 표 위치에 `<!-- TODO: 헤더 확인 -->` 코멘트 남기고 원본 유지.
5. **양식 shape 삭제** (template_shape_removed): 사용자가 지운 로고/이미지 slot 에
   대응하는 MD 내용(특정 단락·부제)이 있으면 제거.
6. **줄글 매핑 실패** (prose_unmapped):
   - 줄글이 길면 3~5개 bullet 으로 요약 (핵심 명사구·수치 위주)
   - 이미 bullet 인데 양식에 들어갈 shape 가 없으면 헤딩 구조 재편 고려.
7. **빈 body slot** (body_slot_empty): 해당 섹션에 한 줄 요약 또는 bullet 1~3개 추가.
   창작 금지 — 원본에 근거 없으면 `[TBD]` 표시만.
8. 출력은 **완성된 MD 전문** 1개. diff 아님. 코드펜스 금지.
9. 설명·메타코멘트 금지. MD 본문만.
"""


def _format_issues(issues: list[dict]) -> str:
    lines: list[str] = []
    for i, iss in enumerate(issues, start=1):
        t = iss.get("type", "?")
        desc = {
            "table_overflow": f"슬라이드 {iss.get('slide')}의 표: {iss.get('rows_used')}행 > 수용 {iss.get('rows_capacity_est')}행 ({iss.get('excess_rows')}행 초과). {iss.get('suggestion', '')}",
            "cell_clip": f"슬라이드 {iss.get('slide')} 셀[{iss.get('row')},{iss.get('col')}]: {iss.get('chars')}자 > {iss.get('capacity_est')}자. 내용: {iss.get('excerpt', '')!r}",
            "text_clip": f"슬라이드 {iss.get('slide')} 텍스트 shape: {iss.get('chars')}자 > {iss.get('capacity_est')}자. 내용: {iss.get('excerpt', '')!r}",
            "unmatched_table": f"MD 표 {iss.get('md_table_idx')}: 양식 테이블과 헤더 매칭 실패",
            "template_shape_removed": f"슬라이드 {iss.get('slide')}: 양식에서 '{iss.get('shape_name')}' 제거됨 (사용자 수기 편집)",
            "prose_unmapped": f"헤딩 '{iss.get('heading')}' 의 {iss.get('kind')} 블록이 양식 body shape 에 매핑 안 됨. 내용: {iss.get('excerpt', '')!r}",
            "body_slot_empty": f"슬라이드 {iss.get('slide')}: 양식에 body shape 있지만 MD 에 해당 내용 없음",
        }.get(t, str(iss))
        lines.append(f"{i}. [{t}] {desc}")
    return "\n".join(lines)


def _user_prompt(
    md_text: str,
    issues: list[dict],
    plan_text: str,
    user_hint: str | None,
) -> str:
    parts: list[str] = []
    parts.append("## 변환 결과 문제")
    parts.append(_format_issues(issues) if issues else "(감지된 문제 없음 — 사용자 힌트만 반영)")
    parts.append("")

    if plan_text:
        parts.append("## 현재 매핑 계획 (참고)")
        parts.append("```")
        parts.append(plan_text[:2000])
        parts.append("```")
        parts.append("")

    if user_hint and user_hint.strip():
        parts.append("## 사용자 추가 힌트")
        parts.append(user_hint.strip())
        parts.append("")

    parts.append("## 원본 MD")
    parts.append("```markdown")
    parts.append(md_text)
    parts.append("```")
    parts.append("")
    parts.append("위 문제와 힌트를 반영한 **수정된 MD 전문** 을 출력하세요. 원본 톤 유지. 코드펜스·설명 금지.")
    return "\n".join(parts)


def _strip_fences(text: str) -> str:
    import re
    s = text.strip()
    s = re.sub(r"^```(?:markdown|md)?\s*\n", "", s)
    s = re.sub(r"\n```\s*$", "", s)
    return s


async def refine_md(
    md_path: str,
    issues: list[dict],
    plan_text: str = "",
    user_hint: str | None = None,
) -> AsyncIterator[str]:
    """LLM 호출해 새 MD 를 스트리밍."""
    md_text = Path(md_path).read_text(encoding="utf-8", errors="replace")
    prompt = _user_prompt(md_text, issues, plan_text, user_hint)
    provider = get_provider()
    async for chunk in provider.generate_text(prompt, system=REFINER_SYSTEM):
        yield chunk


def save_suggested_md(md_path: str, suggested_text: str, output_dir: str | None = None) -> str:
    """LLM 이 뱉은 MD 를 `{앞3자}_suggested_{ts}.md` 로 저장.
    output_dir 지정 시 그 폴더에, 없으면 입력과 같은 폴더에. 코드펜스 제거 후.
    """
    import time as _time
    from backend.services.pptx_slide_composer import short_stem
    p = Path(md_path)
    ts = _time.strftime("%y%m%d_%H%M%S")
    name = f"{short_stem(p.stem)}_suggested_{ts}.md"
    out_dir = Path(output_dir) if output_dir else p.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / name
    cleaned = _strip_fences(suggested_text)
    out.write_text(cleaned, encoding="utf-8")
    return str(out)
