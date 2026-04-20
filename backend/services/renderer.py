from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hwp_mcp.hwpx_vision.tools.render_hwp import render_hwp_to_images  # noqa: E402


def render(source: str, dpi: int = 150, out_dir: str | None = None) -> list[str]:
    return render_hwp_to_images(source, dpi=dpi, out_dir=out_dir)
