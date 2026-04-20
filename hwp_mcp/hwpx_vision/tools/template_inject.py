from __future__ import annotations

from pathlib import Path
from typing import Any

from ..lib.hwpx_template import extract_headings, render_from_template
from ..lib.md_clean import clean_markdown


def list_headings(template_hwpx: str) -> list[dict[str, Any]]:
    sections = extract_headings(template_hwpx)
    return [
        {"heading": s.heading_text, "level": s.heading_level, "body_paragraphs": len(s.body_indices)}
        for s in sections
    ]


def inject_to_template(
    template_hwpx: str,
    section_to_body: dict[str, str],
    output_hwpx: str,
) -> dict[str, Any]:
    if not Path(template_hwpx).exists():
        raise FileNotFoundError(template_hwpx)
    Path(output_hwpx).parent.mkdir(parents=True, exist_ok=True)
    cleaned = {title: clean_markdown(body) for title, body in section_to_body.items()}
    return render_from_template(template_hwpx, cleaned, output_hwpx)
