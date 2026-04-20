"""LLM이 뱉은 Markdown을 HWPX 본문용 평문으로 정리한다."""
from __future__ import annotations

import re


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+)$")
HR_RE = re.compile(r"^\s*(-{3,}|={3,}|\*{3,})\s*$")
BULLET_RE = re.compile(r"^(\s*)[\*\-]\s+(.+)$")
ORDERED_RE = re.compile(r"^(\s*)\d+\.\s+(.+)$")


def _transform_bullet(line: str) -> str:
    """* / - 를 '- '로, 중첩 들여쓰기 유지."""
    m = BULLET_RE.match(line)
    if m:
        indent, content = m.group(1), m.group(2)
        depth = len(indent) // 2
        marker = "○" if depth == 0 else "-"
        return f"{indent}{marker} {content}"
    return line


def clean_markdown(text: str) -> str:
    """
    Markdown 마커를 제거/변환한다:
    - ## 제목 → 제목 (강조 단락으로 처리)
    - **bold** → bold (한/글에서 후편집 권장)
    - `code` → code
    - --- / === → 빈 줄 제거
    - * / - 목록 → ○/- 불릿
    - 1. 목록 → 유지
    - ``` 코드 블록 → 내용만 남김
    """
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue

        if HR_RE.match(line):
            continue

        m = HEADING_RE.match(line)
        if m:
            out.append(m.group(1).strip())
            continue

        line = BOLD_RE.sub(r"\1", line)
        line = INLINE_CODE_RE.sub(r"\1", line)
        line = ITALIC_RE.sub(r"\1", line)

        line = _transform_bullet(line)

        out.append(line)

    result: list[str] = []
    prev_blank = False
    for ln in out:
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        result.append(ln)
        prev_blank = is_blank

    return "\n".join(result).strip()
