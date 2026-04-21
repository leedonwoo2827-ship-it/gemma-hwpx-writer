"""
HWPX 템플릿 조작: ZIP 해제 → section XML 파싱 → 섹션별 본문 교체 → 재압축.

HWPX 구조:
- ZIP 아카이브
- Contents/section0.xml (본문)
  - <hp:p> 단락 요소들
    - paraPrIDRef 속성으로 단락 스타일 참조
    - <hp:run> 내부에 <hp:t> 텍스트
- 헤딩 판별은 텍스트 패턴으로: "1.", "2.", "가.", "나.", "A.", "B." 등
"""
from __future__ import annotations

import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree


NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
}
for prefix, uri in NS.items():
    etree.register_namespace(prefix, uri)

HEADING_PATTERNS = [
    re.compile(r"^\s*(\d+)\.\s+(.+)$"),              # 1. ... (공백 필수)
    re.compile(r"^\s*([가-힣])\.\s+(.+)$"),           # 가. ...
    re.compile(r"^\s*([A-Z])\.\s+(.+)$"),            # A. ...
    re.compile(r"^\s*\(([가-힣\d])\)\s+(.+)$"),      # (1) (가)
]
DATE_RE = re.compile(r"^\s*\d{2,4}\.\d{1,2}")
TOC_TAIL_RE = re.compile(r"\s+\d{1,3}\s*$")  # 끝에 페이지번호


def _paragraph_text(p_elem: etree._Element) -> str:
    texts = p_elem.xpath(".//hp:t/text()", namespaces=NS)
    return "".join(texts).strip()


def _is_heading(text: str) -> bool:
    if not text or len(text) > 80:
        return False
    if DATE_RE.match(text):
        return False
    for pat in HEADING_PATTERNS:
        if pat.match(text):
            return True
    return False


def _heading_level(text: str) -> int:
    if re.match(r"^\s*\d+\.\s+", text):
        return 1
    if re.match(r"^\s*[가-힣]\.\s+", text):
        return 2
    if re.match(r"^\s*[A-Z]\.\s+", text):
        return 3
    if re.match(r"^\s*\([가-힣\d]\)\s+", text):
        return 4
    return 5


def _strip_toc_page(text: str) -> str:
    return TOC_TAIL_RE.sub("", text).strip()


@dataclass
class Section:
    heading_text: str
    heading_level: int
    heading_index: int
    body_indices: list[int] = field(default_factory=list)


TABLE_LOCALNAMES = {"tbl", "tc", "cellzonelist"}


def _is_inside_table(p_elem: etree._Element) -> bool:
    """단락이 <hp:tbl>/<hp:tc> 등 표 구조 안에 있는지 확인."""
    parent = p_elem.getparent()
    while parent is not None:
        if etree.QName(parent).localname in TABLE_LOCALNAMES:
            return True
        parent = parent.getparent()
    return False


def parse_sections(section_xml_path: Path) -> tuple[etree._ElementTree, list[etree._Element], list[Section]]:
    tree = etree.parse(str(section_xml_path))
    root = tree.getroot()
    # 표 내부 단락 제외 (표 구조 보존)
    paragraphs = [p for p in root.xpath(".//hp:p", namespaces=NS) if not _is_inside_table(p)]

    sections: list[Section] = []
    current: Optional[Section] = None
    for i, p in enumerate(paragraphs):
        text = _paragraph_text(p)
        if _is_heading(text):
            if current is not None:
                sections.append(current)
            current = Section(
                heading_text=text,
                heading_level=_heading_level(text),
                heading_index=i,
            )
        elif current is not None and text:
            current.body_indices.append(i)
    if current is not None:
        sections.append(current)

    return tree, paragraphs, sections


LAYOUT_CACHE_LOCALNAMES = {"linesegarray", "lineSegArray", "linesegArray"}


def _strip_layout_cache(elem: etree._Element) -> None:
    """
    <hp:linesegarray> 등 HWPX 라인 배치 캐시 제거.
    이 요소는 문서가 마지막으로 열렸을 때의 라인 위치를 절대좌표로 들고 있어서,
    복제해서 새 텍스트를 넣으면 원본 자리에 덮어쓰인다. 제거하면 한/글이 다시 계산.
    """
    to_remove = []
    for child in elem.iter():
        tag = etree.QName(child).localname
        if tag in LAYOUT_CACHE_LOCALNAMES:
            to_remove.append(child)
    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)


def _clone_as_template(p_elem: etree._Element) -> etree._Element:
    """기존 단락을 복제해 템플릿으로 사용 (스타일 유지, 위치 캐시 제거)."""
    clone = etree.fromstring(etree.tostring(p_elem))
    _strip_layout_cache(clone)
    for t in clone.xpath(".//hp:t", namespaces=NS):
        t.text = ""
    return clone


def _set_paragraph_text(p_elem: etree._Element, text: str) -> None:
    """단락 내부의 첫 <hp:t>에 text를 설정. 없으면 runs를 정리하고 새로 만듦."""
    ts = p_elem.xpath(".//hp:t", namespaces=NS)
    if ts:
        ts[0].text = text
        for extra in ts[1:]:
            extra.text = ""
    else:
        runs = p_elem.xpath(".//hp:run", namespaces=NS)
        if runs:
            t = etree.SubElement(runs[0], f"{{{NS['hp']}}}t")
            t.text = text


def _line_marker(text: str) -> str:
    """라인의 머리 기호 반환. '○', '-', '·', '•', 아니면 ''."""
    s = text.lstrip()
    for m in ("○", "•", "·", "-"):
        if s.startswith(m):
            return m
    return ""


def _build_template_library(
    body_elems: list[etree._Element],
) -> tuple[dict[str, etree._Element], etree._Element]:
    """섹션의 기존 본문 단락에서 머리 기호별 스타일 템플릿을 수집."""
    by_marker: dict[str, etree._Element] = {}
    for p in body_elems:
        txt = _paragraph_text(p)
        if not txt:
            continue
        m = _line_marker(txt)
        if m not in by_marker:
            by_marker[m] = p
    default = body_elems[0] if body_elems else None
    return by_marker, default  # type: ignore[return-value]


def inject_section_body(
    section_xml_path: Path,
    section_to_body: dict[str, str],
    template_for_body: Optional[etree._Element] = None,
) -> None:
    """
    section_to_body: {heading_text: new_body_text}. 여러 단락은 \\n 으로 구분.
    기존 body 단락들을 삭제하고 생성 텍스트를 새 단락으로 삽입.
    각 라인의 머리 기호(○, -, 없음)에 맞춰 원본에서 해당 스타일의 단락을 찾아 템플릿으로 씀.
    """
    tree, paragraphs, sections = parse_sections(section_xml_path)

    for sec in sections:
        new_body = section_to_body.get(sec.heading_text)
        if new_body is None or not sec.body_indices:
            continue

        body_elems = [paragraphs[i] for i in sec.body_indices]
        first_body_elem = body_elems[0]
        marker_templates, default_template = _build_template_library(body_elems)

        parent = first_body_elem.getparent()
        if parent is None:
            continue
        insert_idx = list(parent).index(first_body_elem)

        for elem in body_elems:
            if elem.getparent() is parent:
                parent.remove(elem)

        lines = [ln for ln in new_body.split("\n") if ln.strip()]
        for offset, line in enumerate(lines):
            marker = _line_marker(line)
            tpl_src = (
                template_for_body
                or marker_templates.get(marker)
                or marker_templates.get("")
                or default_template
            )
            new_p = etree.fromstring(etree.tostring(tpl_src))
            _strip_layout_cache(new_p)
            for t in new_p.xpath(".//hp:t", namespaces=NS):
                t.text = ""
            _set_paragraph_text(new_p, line)
            parent.insert(insert_idx + offset, new_p)

    tree.write(str(section_xml_path), xml_declaration=True, encoding="UTF-8", standalone=True)


def extract_headings(hwpx_path: str) -> list[Section]:
    """HWPX 파일의 모든 section XML에서 헤딩 목록을 뽑아낸다."""
    all_sections: list[Section] = []
    with tempfile.TemporaryDirectory() as tmp:
        _extract(hwpx_path, tmp)
        for section_xml in _find_all_section_xmls(tmp):
            _, _, sections = parse_sections(section_xml)
            all_sections.extend(sections)
    return all_sections


def _extract(hwpx_path: str, dest: str) -> None:
    with zipfile.ZipFile(hwpx_path, "r") as z:
        z.extractall(dest)


def _find_all_section_xmls(root_dir: str) -> list[Path]:
    contents = Path(root_dir) / "Contents"
    candidates = sorted(contents.glob("section*.xml"))
    if not candidates:
        raise FileNotFoundError(f"section*.xml을 {contents} 에서 찾지 못했습니다.")
    return candidates


def _repack(source_dir: str, output_path: str) -> None:
    src = Path(source_dir)
    out = Path(output_path)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        mimetype = src / "mimetype"
        if mimetype.exists():
            z.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(src).as_posix()
            if rel == "mimetype":
                continue
            z.write(p, rel)


def _pick_canonical_body_template(
    all_section_xmls: list[Path],
) -> Optional[etree._Element]:
    """
    문서 전체에서 '가장 먼저 나오는 본문 단락' 하나를 반환.
    기호 우선순위 없이 문서 순서 그대로. 모든 섹션의 모든 라인이 이 스타일을 재사용 (일괄 통일).
    """
    for sx in all_section_xmls:
        _, paragraphs, sections = parse_sections(sx)
        for sec in sections:
            for idx in sec.body_indices:
                p = paragraphs[idx]
                if _paragraph_text(p):
                    return _strip_and_clear(etree.fromstring(etree.tostring(p)))
    return None


def _strip_and_clear(p: Optional[etree._Element]) -> Optional[etree._Element]:
    if p is None:
        return None
    _strip_layout_cache(p)
    for t in p.xpath(".//hp:t", namespaces=NS):
        t.text = ""
    return p


def render_from_template(
    template_hwpx: str,
    section_to_body: dict[str, str],
    output_hwpx: str,
) -> dict:
    """
    템플릿 HWPX를 열어 모든 section XML을 순회하며 매칭되는 섹션 본문을 교체.
    문서 전체에 걸쳐 하나의 캐노니컬 템플릿 단락 스타일을 사용해 일관성 유지.
    """
    replaced = 0
    with tempfile.TemporaryDirectory() as tmp:
        _extract(template_hwpx, tmp)
        section_xmls = _find_all_section_xmls(tmp)
        canonical = _pick_canonical_body_template(section_xmls)
        for section_xml in section_xmls:
            _, _, sections = parse_sections(section_xml)
            matching = {s.heading_text: section_to_body[s.heading_text] for s in sections if s.heading_text in section_to_body}
            if not matching:
                continue
            inject_section_body(section_xml, matching, template_for_body=canonical)
            replaced += len(matching)
        _repack(tmp, output_hwpx)
    size = Path(output_hwpx).stat().st_size
    return {"path": output_hwpx, "bytes": size, "sections_replaced": replaced}
