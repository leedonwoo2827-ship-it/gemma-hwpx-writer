from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fastapi.responses import StreamingResponse

from backend.services.mcp_bridge import call_analyze_style, call_apply_style
from backend.services.renderer import render
from backend.services.section_composer import compose_section
from backend.services.composer import compose_with_template_headings

import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from doc_mcp.hwpx_vision.tools.template_inject import list_headings, inject_to_template
from doc_mcp.hwpx_vision.lib.md_sections import parse_md_sections, match_to_template_headings


router = APIRouter(prefix="/api", tags=["hwpx"])


class HeadingsBody(BaseModel):
    template_hwpx: str


@router.post("/template/headings")
def template_headings(body: HeadingsBody) -> dict[str, Any]:
    if not Path(body.template_hwpx).exists():
        raise HTTPException(404, "템플릿 HWPX 없음")
    try:
        headings = list_headings(body.template_hwpx)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"헤딩 추출 실패: {type(e).__name__}: {e}")
    return {"headings": headings}


def _load_sources(md_paths: list[str]) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for p in md_paths:
        pp = Path(p)
        if not pp.exists():
            raise HTTPException(404, f"MD 없음: {p}")
        sources.append((pp.stem, pp.read_text(encoding="utf-8")))
    if not sources:
        raise HTTPException(400, "최소 1개 MD 필요")
    return sources


class TemplateInjectBody(BaseModel):
    template_hwpx: str
    output_hwpx: str
    source_md_paths: list[str]
    heading_filter: list[str] | None = None


@router.post("/template/inject")
async def template_inject(body: TemplateInjectBody):
    if not Path(body.template_hwpx).exists():
        raise HTTPException(404, "템플릿 없음")
    sources = _load_sources(body.source_md_paths)

    try:
        headings = list_headings(body.template_hwpx)
    except Exception as e:
        raise HTTPException(500, f"헤딩 추출 실패: {e}")

    seen: set[str] = set()
    targets: list[str] = []
    for h in headings:
        text = h["heading"]
        if h["body_paragraphs"] < 3:
            continue
        if text in seen:
            continue
        seen.add(text)
        targets.append(text)
    if body.heading_filter:
        targets = [t for t in targets if t in body.heading_filter]

    async def stream():
        section_map: dict[str, str] = {}
        try:
            yield f"event: start\ndata: {len(targets)}\n\n"
            for i, title in enumerate(targets, 1):
                yield f"event: section_begin\ndata: {i}/{len(targets)}::{title}\n\n"
                body_text = await compose_section(title, sources)
                section_map[title] = body_text
                preview = body_text[:80].replace("\n", " ")
                yield f"event: section_done\ndata: {i}/{len(targets)}::{title}::{preview}\n\n"
            yield f"event: injecting\ndata: {body.output_hwpx}\n\n"
            result = inject_to_template(body.template_hwpx, section_map, body.output_hwpx)
            yield f"event: done\ndata: {result['path']}|{result['bytes']}|{result['sections_replaced']}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class DraftMdBody(BaseModel):
    template_hwpx: str
    output_md: str
    source_md_paths: list[str]


@router.post("/template/draft-md")
async def template_draft_md(body: DraftMdBody):
    """
    템플릿 HWPX의 헤딩 구조 + N개 소스 MD를 합성해 완성형 MD 생성.
    사용자 검수용. LLM 1회 호출.
    """
    if not Path(body.template_hwpx).exists():
        raise HTTPException(404, "템플릿 없음")
    sources = _load_sources(body.source_md_paths)

    try:
        headings = list_headings(body.template_hwpx)
    except Exception as e:
        raise HTTPException(500, f"헤딩 추출 실패: {e}")

    import re as _re
    toc_tail = _re.compile(r"\s+\d{1,3}\s*$")
    by_norm: dict[str, dict] = {}
    for h in headings:
        norm = toc_tail.sub("", h["heading"]).strip()
        existing = by_norm.get(norm)
        if existing is None or h.get("body_paragraphs", 0) > existing.get("body_paragraphs", 0):
            by_norm[norm] = {**h, "heading": norm}
    filtered = list(by_norm.values())

    out = Path(body.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)

    async def stream():
        collected: list[str] = []
        try:
            yield f"event: start\ndata: {len(filtered)}\n\n"
            async for chunk in compose_with_template_headings(filtered, sources):
                collected.append(chunk)
                safe = chunk.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            out.write_text("".join(collected), encoding="utf-8")
            yield f"event: done\ndata: {out}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class InjectFromMdBody(BaseModel):
    template_hwpx: str
    md_path: str
    output_hwpx: str
    style_hwpx: str | None = None


@router.post("/template/inject-from-md")
def template_inject_from_md(body: InjectFromMdBody) -> dict[str, Any]:
    """
    이미 작성된 MD를 템플릿 헤딩에 매칭해 주입. LLM 호출 없음.

    style_hwpx 지정 시: 본문 단락 스타일을 이 파일에서 차용한다
      (글쓰기 주입 = template_hwpx, 디자인 주입 = style_hwpx 로 역할 분리).
    """
    if not Path(body.template_hwpx).exists():
        raise HTTPException(404, "템플릿 없음")
    if not Path(body.md_path).exists():
        raise HTTPException(404, "MD 없음")

    md_text = Path(body.md_path).read_text(encoding="utf-8")
    md_sections = parse_md_sections(md_text)

    try:
        headings = list_headings(body.template_hwpx)
    except Exception as e:
        raise HTTPException(500, f"헤딩 추출 실패: {e}")

    template_heading_texts = [h["heading"] for h in headings if h["body_paragraphs"] >= 3]
    section_map = match_to_template_headings(md_sections, template_heading_texts)

    if not section_map:
        raise HTTPException(400, f"MD 헤딩({len(md_sections)})과 템플릿 헤딩({len(template_heading_texts)}) 매칭 실패")

    try:
        result = inject_to_template(
            body.template_hwpx,
            section_map,
            body.output_hwpx,
            style_source_hwpx=body.style_hwpx,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"주입 실패: {e}")
    return {
        **result,
        "matched_sections": list(section_map.keys()),
        "md_sections_total": len(md_sections),
        "style_source": body.style_hwpx,
    }


class AnalyzeBody(BaseModel):
    reference_source: str
    use_cache: bool = True
    pages: int = 3


class ConvertBody(BaseModel):
    md_path: str
    output_hwpx: str
    reference_source: str | None = None
    style_json: dict[str, Any] | None = None


@router.post("/analyze-style")
def analyze_style(body: AnalyzeBody) -> dict[str, Any]:
    src = Path(body.reference_source)
    if not src.exists():
        raise HTTPException(404, f"참조 파일 없음: {src}")
    try:
        images = render(str(src))
    except Exception as e:
        raise HTTPException(500, f"이미지 렌더링 실패: {e}")
    images = images[: max(1, body.pages)]
    style = call_analyze_style(image_paths=images, use_cache=body.use_cache)
    return {"style_json": style, "pages_used": images}


@router.post("/md-to-hwpx")
def md_to_hwpx(body: ConvertBody) -> dict[str, Any]:
    if not Path(body.md_path).exists():
        raise HTTPException(404, f"MD 없음: {body.md_path}")

    style = body.style_json
    if style is None and body.reference_source:
        ref = Path(body.reference_source)
        if ref.exists():
            try:
                images = render(str(ref))[:3]
                style = call_analyze_style(image_paths=images, use_cache=True)
            except Exception:
                style = None

    try:
        result = call_apply_style(md_path=body.md_path, output_hwpx=body.output_hwpx, style_json=style)
    except Exception as e:
        raise HTTPException(500, f"HWPX 변환 실패: {e}")
    return result
