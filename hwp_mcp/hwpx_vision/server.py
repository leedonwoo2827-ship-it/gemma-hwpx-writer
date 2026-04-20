from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .tools.analyze_style import analyze_style_from_image as _analyze
from .tools.apply_style import apply_style_to_md as _apply
from .tools.render_hwp import render_hwp_to_images as _render


app = FastMCP("hwpx_vision")


@app.tool()
def analyze_style_from_image(
    image_paths: list[str],
    use_cache: bool = True,
    model: str | None = None,
) -> dict[str, Any]:
    """참조 문서 페이지 이미지(PNG)에서 헤딩/본문/표/여백 스타일을 추출해 StyleJSON으로 반환한다."""
    return _analyze(image_paths=image_paths, use_cache=use_cache, model=model)


@app.tool()
def apply_style_to_md(
    md_path: str,
    output_hwpx: str,
    style_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Markdown 파일과 StyleJSON을 합쳐 HWPX 파일로 저장한다. style_json 생략 시 기본 프리셋 사용."""
    return _apply(md_path=md_path, style_json=style_json, output_hwpx=output_hwpx)


@app.tool()
def render_hwp_to_images(
    source_path: str,
    dpi: int = 150,
    out_dir: str | None = None,
) -> list[str]:
    """HWP/HWPX/PDF를 페이지별 PNG로 렌더링한다. HWP는 LibreOffice(soffice) 필요."""
    return _render(source_path=source_path, dpi=dpi, out_dir=out_dir)


if __name__ == "__main__":
    app.run()
