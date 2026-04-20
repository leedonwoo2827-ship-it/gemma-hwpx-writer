from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.composer import compose_report


router = APIRouter(prefix="/api", tags=["report"])


class ComposeBody(BaseModel):
    source_md_paths: list[str] | None = None
    output_md: str
    plan_md: str | None = None
    workplan_md: str | None = None
    wrapup_md: str | None = None


def _collect_sources(body: ComposeBody) -> list[tuple[str, str]]:
    paths: list[str] = []
    if body.source_md_paths:
        paths = list(body.source_md_paths)
    else:
        for p in (body.plan_md, body.workplan_md, body.wrapup_md):
            if p:
                paths.append(p)
    sources: list[tuple[str, str]] = []
    for p in paths:
        pp = Path(p)
        if not pp.exists():
            raise HTTPException(404, f"MD 없음: {p}")
        sources.append((pp.stem, pp.read_text(encoding="utf-8")))
    if not sources:
        raise HTTPException(400, "최소 1개 MD 필요")
    return sources


@router.post("/compose")
async def compose(body: ComposeBody):
    sources = _collect_sources(body)
    out = Path(body.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)

    async def event_stream():
        collected: list[str] = []
        try:
            async for chunk in compose_report(sources):
                collected.append(chunk)
                safe = chunk.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            out.write_text("".join(collected), encoding="utf-8")
            yield f"event: done\ndata: {out}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {e}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
