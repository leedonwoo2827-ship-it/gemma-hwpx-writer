from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _soffice() -> str | None:
    for candidate in ("soffice", "soffice.exe", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            return path
    for p in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(p).exists():
            return p
    return None


def _convert_to_pdf(source: str, out_dir: str) -> str:
    soffice = _soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice(soffice)를 찾을 수 없습니다. HWP 렌더링에는 LibreOffice가 필요합니다. "
            "또는 소스 파일을 미리 PDF로 변환해 주세요."
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, source],
        check=True,
        timeout=120,
    )
    stem = Path(source).stem
    pdf = Path(out_dir) / f"{stem}.pdf"
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice PDF 변환 실패: {source}")
    return str(pdf)


def render_hwp_to_images(source_path: str, dpi: int = 150, out_dir: str | None = None) -> list[str]:
    """
    HWP/HWPX/PDF를 페이지 단위 PNG로 렌더링.
    PDF는 바로, HWP/HWPX는 LibreOffice로 PDF 변환 후 렌더링.
    """
    import fitz  # PyMuPDF

    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(source_path)

    work_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="hwpx_render_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = str(src)
    if src.suffix.lower() in (".hwp", ".hwpx"):
        pdf_path = _convert_to_pdf(str(src), str(work_dir))

    out_paths: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc):
            png = work_dir / f"{src.stem}_p{i + 1}.png"
            page.get_pixmap(matrix=matrix, alpha=False).save(str(png))
            out_paths.append(str(png))
    finally:
        doc.close()
    return out_paths
