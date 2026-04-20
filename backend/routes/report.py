from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.composer import compose_report


router = APIRouter(prefix="/api", tags=["report"])


class ComposeBody(BaseModel):
    plan_md: str
    workplan_md: str
    wrapup_md: str
    output_md: str


@router.post("/compose")
async def compose(body: ComposeBody):
    for p in (body.plan_md, body.workplan_md, body.wrapup_md):
        if not Path(p).exists():
            raise HTTPException(404, f"MD 없음: {p}")

    plan_text = Path(body.plan_md).read_text(encoding="utf-8")
    workplan_text = Path(body.workplan_md).read_text(encoding="utf-8")
    wrapup_text = Path(body.wrapup_md).read_text(encoding="utf-8")
    out = Path(body.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)

    async def event_stream():
        collected: list[str] = []
        try:
            async for chunk in compose_report(plan_text, workplan_text, wrapup_text):
                collected.append(chunk)
                safe = chunk.replace("\r", "").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            out.write_text("".join(collected), encoding="utf-8")
            yield f"event: done\ndata: {out}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {e}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
