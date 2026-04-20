"""MCP 서버를 직접 import해 호출한다 (stdio 대신 in-process)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hwp_mcp.hwpx_vision.tools.analyze_style import analyze_style_from_image
from hwp_mcp.hwpx_vision.tools.apply_style import apply_style_to_md


def call_analyze_style(image_paths: list[str], use_cache: bool = True) -> dict[str, Any]:
    return analyze_style_from_image(image_paths=image_paths, use_cache=use_cache)


def call_apply_style(md_path: str, output_hwpx: str, style_json: dict[str, Any] | None = None) -> dict[str, Any]:
    return apply_style_to_md(md_path=md_path, style_json=style_json, output_hwpx=output_hwpx)
