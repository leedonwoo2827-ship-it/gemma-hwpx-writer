from __future__ import annotations

from pathlib import Path
from typing import Any

from ..lib.hwpx_writer import render_md_to_hwpx
from ..lib.style_schema import StyleJSON, default_preset


def apply_style_to_md(
    md_path: str,
    style_json: dict[str, Any] | None,
    output_hwpx: str,
) -> dict[str, Any]:
    md_text = Path(md_path).read_text(encoding="utf-8")
    if style_json:
        style = StyleJSON.model_validate(style_json)
    else:
        style = default_preset()

    Path(output_hwpx).parent.mkdir(parents=True, exist_ok=True)
    return render_md_to_hwpx(md_text, style, output_hwpx)
