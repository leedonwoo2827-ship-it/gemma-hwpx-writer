"""kordoc 서브프로세스 호출. 없으면 파일 확장자로 간단한 폴백."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _kordoc_cli() -> str | None:
    for name in ("kordoc", "kordoc.cmd"):
        path = shutil.which(name)
        if path:
            return path
    local = Path(__file__).resolve().parents[2] / "mcp" / "kordoc" / "dist" / "cli.js"
    if local.exists():
        node = shutil.which("node")
        if node:
            return f"{node}:{local}"
    return None


def convert_to_md(source: str, out_md: str) -> str:
    """HWP/HWPX/PDF/DOCX 등을 MD로 변환. kordoc 없으면 PDF만 간단 추출."""
    cli = _kordoc_cli()
    if cli:
        if cli.startswith(shutil.which("node") or "node"):
            node, script = cli.split(":", 1)
            cmd = [node, script, source, "-o", out_md]
        else:
            cmd = [cli, source, "-o", out_md]
        subprocess.run(cmd, check=True, timeout=120)
        return out_md

    src = Path(source)
    if src.suffix.lower() == ".pdf":
        import fitz
        doc = fitz.open(str(src))
        try:
            lines: list[str] = [f"# {src.stem}\n"]
            for i, page in enumerate(doc):
                lines.append(f"\n## p.{i + 1}\n")
                lines.append(page.get_text("text"))
        finally:
            doc.close()
        Path(out_md).write_text("\n".join(lines), encoding="utf-8")
        return out_md

    if src.suffix.lower() == ".md":
        Path(out_md).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return out_md

    raise RuntimeError(
        f"kordoc CLI를 찾을 수 없고 {src.suffix} 폴백이 없습니다. "
        "mcp/kordoc을 설치하거나 PDF/MD로 변환해 주세요."
    )
