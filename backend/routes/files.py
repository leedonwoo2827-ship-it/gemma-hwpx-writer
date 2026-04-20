from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.services.kordoc_client import convert_to_md


router = APIRouter(prefix="/api", tags=["files"])


class TreeQuery(BaseModel):
    root: str


class ConvertBody(BaseModel):
    source: str


def _walk(root: Path, base: Path) -> dict[str, Any]:
    rel = root.relative_to(base).as_posix() if root != base else ""
    node: dict[str, Any] = {"name": root.name or str(root), "path": str(root), "rel": rel}
    if root.is_dir():
        node["type"] = "dir"
        children = []
        try:
            entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            entries = []
        for child in entries:
            if child.name.startswith(".") or child.name in ("node_modules", "__pycache__"):
                continue
            children.append(_walk(child, base))
        node["children"] = children
    else:
        node["type"] = "file"
        node["ext"] = root.suffix.lower()
    return node


@router.get("/tree")
def get_tree(root: str) -> dict[str, Any]:
    try:
        p = Path(root).resolve()
    except Exception as e:
        raise HTTPException(400, f"경로 해석 실패: {e}")
    if not p.exists():
        raise HTTPException(404, f"경로 없음: {root}")
    try:
        return _walk(p, p)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"트리 탐색 실패: {type(e).__name__}: {e}")


@router.get("/file")
def read_file(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "파일 없음")
    if p.suffix.lower() not in (".md", ".txt"):
        raise HTTPException(400, "MD/TXT만 미리보기 가능")
    return {"path": str(p), "content": p.read_text(encoding="utf-8")}


@router.post("/convert-md")
def convert_md(body: ConvertBody) -> dict[str, Any]:
    src = Path(body.source)
    if not src.exists():
        raise HTTPException(404, "원본 파일 없음")
    out = src.with_suffix(".md")
    try:
        convert_to_md(str(src), str(out))
    except Exception as e:
        raise HTTPException(500, f"변환 실패: {e}")
    return {"md_path": str(out)}


@router.post("/upload-md")
async def upload_md(dest_dir: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    name = file.filename or "uploaded.md"
    if not name.lower().endswith(".md"):
        name = name + ".md"
    target = dest / name
    target.write_bytes(await file.read())
    return {"md_path": str(target)}
