"""
MD → HWPX 간이 변환 (python-hwpx v2.9 HwpxDocument API 사용).

템플릿 주입 경로가 아닌 "직통 MD → HWPX" 용 폴백. 스타일 정교화는 하지 않고
blank HWPX에 단락만 순차 추가한다. StyleJSON은 힌트로만 참고.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hwpx import HwpxDocument
from markdown_it import MarkdownIt
from markdown_it.token import Token

from .md_clean import clean_markdown
from .style_schema import StyleJSON


def render_md_to_hwpx(md_text: str, style: StyleJSON, output_path: str) -> dict[str, Any]:
    cleaned = clean_markdown(md_text)

    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(cleaned)

    doc = HwpxDocument.new()

    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t.type == "heading_open":
            level = int(t.tag[1])
            inline = tokens[i + 1]
            text = inline.content
            prefix = _heading_prefix(level, style, text)
            doc.add_paragraph(prefix)
            i += 3
            continue

        if t.type == "paragraph_open":
            inline = tokens[i + 1]
            text = inline.content
            if text.strip():
                doc.add_paragraph(text)
            i += 3
            continue

        if t.type in ("bullet_list_open", "ordered_list_open"):
            i = _render_list(doc, tokens, i, ordered=t.type == "ordered_list_open")
            continue

        if t.type == "table_open":
            i = _render_table_as_paragraphs(doc, tokens, i)
            continue

        i += 1

    doc.save(output_path)
    size = Path(output_path).stat().st_size
    return {"path": output_path, "bytes": size}


def _heading_prefix(level: int, style: StyleJSON, text: str) -> str:
    for h in style.heading_levels:
        if h.level == level and h.numbering:
            try:
                return f"{h.numbering.format(n='', m='', k='').strip()} {text}".strip()
            except Exception:
                pass
    return text


def _render_list(doc: Any, tokens: list[Token], i: int, ordered: bool) -> int:
    depth = 0
    counters: list[int] = []
    while i < len(tokens):
        t = tokens[i]
        if t.type in ("bullet_list_open", "ordered_list_open"):
            depth += 1
            counters.append(0)
        elif t.type in ("bullet_list_close", "ordered_list_close"):
            depth -= 1
            if counters:
                counters.pop()
            if depth == 0:
                return i + 1
        elif t.type == "inline":
            marker = "○ " if depth == 1 else "- "
            if ordered and counters:
                counters[-1] += 1
                marker = f"{counters[-1]}. "
            indent = "  " * max(0, depth - 1)
            doc.add_paragraph(f"{indent}{marker}{t.content}")
        i += 1
    return i


def _render_table_as_paragraphs(doc: Any, tokens: list[Token], i: int) -> int:
    """python-hwpx의 add_table은 스타일 의존성이 크므로, 우선은 | 구분자 단락으로 표현."""
    rows: list[list[str]] = []
    current: list[str] = []
    while i < len(tokens):
        t = tokens[i]
        if t.type == "table_close":
            if current:
                rows.append(current)
            break
        if t.type == "tr_open":
            current = []
        elif t.type == "tr_close":
            rows.append(current)
            current = []
        elif t.type == "inline":
            current.append(t.content)
        i += 1
    for row in rows:
        doc.add_paragraph(" | ".join(row))
    return i + 1
