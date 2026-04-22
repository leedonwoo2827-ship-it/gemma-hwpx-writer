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
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _transform_bullet(line: str) -> str:
    """* / - 를 '- '로, 중첩 들여쓰기 유지."""
    m = BULLET_RE.match(line)
    if m:
        indent, content = m.group(1), m.group(2)
        depth = len(indent) // 2
        marker = "○" if depth == 0 else "-"
        return f"{indent}{marker} {content}"
    return line


def _parse_table_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """
    GFM 표 블록을 간결한 한 줄씩 텍스트로 변환 (중간점 · 로 구분).
    반환: (변환된_라인들, 표_끝_인덱스+1)
    """
    table_rows: list[str] = []
    i = start
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        if not stripped or "|" not in stripped:
            break
        table_rows.append(stripped)
        i += 1

    out: list[str] = []
    for row in table_rows:
        if TABLE_SEP_RE.match(row):
            continue
        inner = row.strip().strip("|")
        cells = [c.strip() for c in inner.split("|")]
        cells = [c for c in cells if c]
        if not cells:
            continue
        out.append(" · ".join(cells))
    return out, i


def clean_markdown(text: str) -> str:
    """
    Markdown 마커를 제거/변환한다:
    - ## 제목 → 제목 (강조 단락으로 처리)
    - **bold** → bold
    - `code` → code
    - --- / === (horizontal rule) → 제거
    - * / - 목록 → ○/- 불릿 (깊이에 따라)
    - 1. 순서 목록 → 유지
    - ``` 코드 블록 → 내용만 남김
    - | a | b | GFM 표 → "a · b" 형태로 압축 (문자 깨짐 방지)
    """
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        if line.strip().startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            out.append(line)
            i += 1
            continue

        if "|" in line and line.count("|") >= 2 and i + 1 < len(lines):
            if TABLE_SEP_RE.match(lines[i + 1]):
                converted, end = _parse_table_block(lines, i)
                out.extend(converted)
                i = end
                continue

        if HR_RE.match(line):
            i += 1
            continue

        m = HEADING_RE.match(line)
        if m:
            out.append(m.group(1).strip())
            i += 1
            continue

        line = BOLD_RE.sub(r"\1", line)
        line = INLINE_CODE_RE.sub(r"\1", line)
        line = ITALIC_RE.sub(r"\1", line)

        line = _transform_bullet(line)

        out.append(line)
        i += 1

    result: list[str] = []
    prev_blank = False
    for ln in out:
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        result.append(ln)
        prev_blank = is_blank

    return "\n".join(result).strip()
