"""
PPTX 라우터 v5 — md2pptx-template 엔진.

단일 엔드포인트: POST /api/pptx/convert
  - MD + 양식 PPTX → 결과 PPTX (결정론적, LLM/API 없음)
  - 디자인 byte-level 보존
  - 테이블은 헤더 Jaccard 매칭
  - 미매칭 슬라이드는 기본 삭제 (keep_unused 로 유지 가능)
"""
from __future__ import annotations

import sys
import time as _time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from doc_mcp.md2pptx.cli import convert as md2pptx_convert
from doc_mcp.md2pptx.analyzer import analyze_output


router = APIRouter(prefix="/api/pptx", tags=["pptx"])


class ConvertBody(BaseModel):
    template_pptx: str
    md_path: str
    output_pptx: str | None = None
    dry_run: bool = False
    keep_unused: bool = False


@router.post("/convert")
def pptx_convert(body: ConvertBody) -> dict[str, Any]:
    tpl = Path(body.template_pptx)
    md = Path(body.md_path)
    if not tpl.exists():
        raise HTTPException(404, f"양식 PPTX 없음: {tpl}")
    if not md.exists():
        raise HTTPException(404, f"MD 없음: {md}")
    if tpl.suffix.lower() != ".pptx":
        raise HTTPException(400, f"양식 파일이 PPTX 아님: {tpl.name}")
    if md.suffix.lower() != ".md":
        raise HTTPException(400, f"MD 파일이 .md 아님: {md.name}")

    # 출력 경로 결정 — 파일명은 입력 MD 의 앞 3자만 따고 작업명·timestamp 부착
    if body.output_pptx:
        out = Path(body.output_pptx)
    else:
        from backend.services.pptx_slide_composer import short_stem
        ts = _time.strftime("%y%m%d_%H%M%S")
        out = md.parent / f"{short_stem(md.stem)}_re_{ts}.pptx"

    try:
        result = md2pptx_convert(
            template=str(tpl),
            md=str(md),
            out=str(out),
            dry_run=body.dry_run,
            keep_unused=body.keep_unused,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"변환 실패: {type(e).__name__}: {e}")

    result_size = 0
    if result.get("output_path") and Path(result["output_path"]).exists():
        result_size = Path(result["output_path"]).stat().st_size

    return {
        "output_path": result.get("output_path", ""),
        "bytes": result_size,
        "slides_count": result.get("slides_count", 0),
        "slides_final": result.get("slides_final", []),
        "slides_dropped": result.get("slides_dropped", []),
        "headings_matched": result.get("headings_matched", []),
        "tables_matched": result.get("tables_matched", []),
        "tables_unmatched": result.get("tables_unmatched", []),
        "body_blocks_matched": result.get("body_blocks_matched", []),
        "body_blocks_unmapped": result.get("body_blocks_unmapped", []),
        "plan_text": result.get("plan_text", ""),
        "dry_run": result.get("dry_run", False),
    }


# ─────────────────────────────────────────────────────────
# v6: 결과 분석 + MD 재작성 제안
# ─────────────────────────────────────────────────────────

class AnalyzeBody(BaseModel):
    template_pptx: str
    output_pptx: str
    md_path: str | None = None
    # convert() 가 반환한 메타를 같이 넘기면 tables_unmatched 등까지 감지됨
    convert_result: dict[str, Any] | None = None


@router.post("/analyze")
def pptx_analyze(body: AnalyzeBody) -> dict[str, Any]:
    """결과 PPTX 를 분석해 문제 리스트 반환.
    convert_result 없으면 일부 감지 생략 (구조 기반 overflow/cell_clip 은 가능).
    """
    tpl = Path(body.template_pptx)
    out = Path(body.output_pptx)
    if not out.exists():
        raise HTTPException(404, f"결과 PPTX 없음: {out}")
    try:
        result = analyze_output(
            template_pptx=str(tpl),
            output_pptx=str(out),
            convert_result=body.convert_result,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"분석 실패: {type(e).__name__}: {e}")
    return result


class DraftSlideBody(BaseModel):
    md_path: str
    template_pptx: str
    user_hint: str | None = None


@router.post("/draft-slide-md")
async def pptx_draft_slide_md(body: DraftSlideBody):
    """양식 PPTX 구조 기반으로 MD 를 슬라이드용으로 재구조화.
    SSE 로 스트리밍 + 마지막에 저장된 새 MD 경로 반환.
    변환 전 단계 — 오버플로우·클리핑 예방용.
    """
    from backend.services.pptx_slide_composer import draft_slide_md, save_slide_md

    md_p = Path(body.md_path)
    tpl = Path(body.template_pptx)
    if not md_p.exists():
        raise HTTPException(404, f"MD 없음: {md_p}")
    if not tpl.exists():
        raise HTTPException(404, f"양식 PPTX 없음: {tpl}")
    if tpl.suffix.lower() != ".pptx":
        raise HTTPException(400, f"양식 파일이 PPTX 아님: {tpl.name}")

    async def stream():
        collected: list[str] = []
        try:
            yield "event: start\ndata: 0\n\n"
            async for chunk in draft_slide_md(
                md_path=str(md_p),
                template_pptx=str(tpl),
                user_hint=body.user_hint,
            ):
                collected.append(chunk)
                safe = chunk.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"

            drafted = "".join(collected)
            saved_path = save_slide_md(str(md_p), drafted)
            yield f"event: done\ndata: {saved_path}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = f"{type(e).__name__}: {e}"
            yield f"event: error\ndata: {msg}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class RefineBody(BaseModel):
    md_path: str
    template_pptx: str
    output_pptx: str
    user_hint: str | None = None


@router.post("/refine-md")
async def pptx_refine_md(body: RefineBody):
    """문제 분석 → LLM 이 MD 재작성 → SSE 스트리밍 + 저장된 새 MD 경로 이벤트."""
    from backend.services.pptx_md_refiner import refine_md, save_suggested_md

    md_p = Path(body.md_path)
    if not md_p.exists():
        raise HTTPException(404, f"MD 없음: {md_p}")
    if not Path(body.output_pptx).exists():
        raise HTTPException(404, f"결과 PPTX 없음: {body.output_pptx}")

    # 분석: convert_result 없으면 구조 기반만
    try:
        analysis = analyze_output(
            template_pptx=body.template_pptx,
            output_pptx=body.output_pptx,
            convert_result=None,
        )
    except Exception as e:
        raise HTTPException(500, f"분석 실패: {type(e).__name__}: {e}")
    issues = analysis.get("issues", [])

    async def stream():
        collected: list[str] = []
        try:
            yield f"event: start\ndata: {len(issues)}\n\n"
            async for chunk in refine_md(
                md_path=str(md_p),
                issues=issues,
                plan_text="",
                user_hint=body.user_hint,
            ):
                collected.append(chunk)
                safe = chunk.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"

            suggested = "".join(collected)
            saved_path = save_suggested_md(str(md_p), suggested)
            yield f"event: done\ndata: {saved_path}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = f"{type(e).__name__}: {e}"
            yield f"event: error\ndata: {msg}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
