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


class MoveBody(BaseModel):
    source: str        # 이동할 파일/폴더 절대경로
    target_dir: str    # 옮길 대상 폴더 절대경로
    workspace_root: str  # 트리 루트 (보안: 이 경로 밖으로 못 나가게)


@router.post("/file/move")
def move_file(body: MoveBody) -> dict[str, Any]:
    """파일·폴더를 같은 workspace 내 다른 폴더로 이동.
    보안: source 와 target_dir 모두 workspace_root 안이어야 함. 자기 자신·자손으로 이동 금지.
    """
    import shutil
    try:
        src = Path(body.source).resolve()
        tgt = Path(body.target_dir).resolve()
        root = Path(body.workspace_root).resolve()
    except Exception as e:
        raise HTTPException(400, f"경로 해석 실패: {e}")

    if not src.exists():
        raise HTTPException(404, f"원본 없음: {src}")
    if not tgt.exists() or not tgt.is_dir():
        raise HTTPException(400, f"대상 폴더 아님: {tgt}")

    # 보안: 두 경로 모두 root 하위
    try:
        src.relative_to(root)
        tgt.relative_to(root)
    except ValueError:
        raise HTTPException(403, "workspace 밖으로 이동 금지")

    # 자기 자신 또는 자손 폴더로 이동 금지
    if src == tgt or src in tgt.parents or src == tgt.parent:
        # src == tgt.parent: 같은 폴더 내 이동 (no-op)
        if src == tgt.parent:
            return {"ok": True, "noop": True, "new_path": str(src)}
        raise HTTPException(400, "자기 자신·자손 폴더로 이동할 수 없습니다")

    # 새 경로 = target_dir / source.name
    new_path = tgt / src.name
    if new_path.exists():
        raise HTTPException(409, f"같은 이름의 항목이 이미 있습니다: {new_path.name}")

    try:
        shutil.move(str(src), str(new_path))
    except Exception as e:
        raise HTTPException(500, f"이동 실패: {type(e).__name__}: {e}")

    return {"ok": True, "new_path": str(new_path)}
