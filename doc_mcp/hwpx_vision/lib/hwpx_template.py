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
    """기존 단락을 복제해 템플릿으로 사용 (스타일 유지, 위치 캐시/자동 번호 제거)."""
    clone = etree.fromstring(etree.tostring(p_elem))
    _strip_layout_cache(clone)
    # _strip_auto_numbering 은 파일 뒤쪽 정의 — 런타임 시점엔 이미 로드되어 있음
    try:
        _strip_auto_numbering(clone)
    except NameError:
        pass
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


KNOWN_MARKERS = ("○", "•", "·", "△", "▲", "※", "◦", "–", "—", "-", "▪", "■", "□", "◆", "◇")

CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _classify_line_marker(text: str) -> str:
    """
    한 줄의 마커 유형을 분류해 일관된 키로 반환.
    매칭된 양식 단락을 찾는 데 사용.
    """
    if not text:
        return "PLAIN"
    s = text.lstrip()
    if re.match(r"^\d+\.\s+", s):
        return "L1_NUM"          # 1. xxx
    if re.match(r"^[가-힣]\.\s+", s):
        return "L2_HAN"          # 가. xxx
    if re.match(r"^[A-Z]\.\s+", s):
        return "L3_UPPER"        # A. xxx
    if re.match(r"^\([가-힣\d]\)\s+", s):
        return "L4_PAREN"        # (1) / (가)
    if s and s[0] in CIRCLED_DIGITS:
        return "L5_CIRCLED"      # ① xxx
    if re.match(r"^[ivxIVX]+\.\s+", s):
        return "L6_ROMAN"        # i. xxx / I. xxx
    for m in ("○", "•", "·", "◦"):
        if s.startswith(m):
            return "BULLET_CIRCLE"
    for m in ("△", "▲", "▪", "■", "□"):
        if s.startswith(m):
            return "BULLET_SHAPE"
    for m in ("◆", "◇"):
        if s.startswith(m):
            return "BULLET_DIAMOND"
    if s.startswith("※"):
        return "NOTE"
    if s.startswith("-") or s.startswith("–") or s.startswith("—"):
        return "DASH"
    return "PLAIN"


def _strip_leading_marker(text: str) -> str:
    """선두 머리 기호와 공백 제거 (템플릿 단락이 이미 기호를 자동 렌더하므로 중복 방지)."""
    s = text.lstrip()
    for m in KNOWN_MARKERS:
        if s.startswith(m):
            s = s[len(m):].lstrip()
            return s
    return s


def _line_marker(text: str) -> str:
    """라인의 머리 기호 반환. KNOWN_MARKERS 중 하나, 없으면 ''."""
    s = text.lstrip()
    for m in KNOWN_MARKERS:
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
    marker_templates: Optional[dict[str, etree._Element]] = None,
    default_template: Optional[etree._Element] = None,
) -> None:
    """
    section_to_body: {heading_text: new_body_text}. 여러 단락은 \\n 으로 구분.
    기존 body 단락들을 삭제하고 생성 텍스트를 새 단락으로 삽입.

    marker_templates: 문서 전체에서 뽑은 {marker: paragraph_style_element}
    default_template: 기호 없는 라인에 쓸 기본 템플릿
    둘 다 없으면 섹션 내부에서 자체적으로 찾음 (하위 호환).
    """
    tree, paragraphs, sections = parse_sections(section_xml_path)

    for sec in sections:
        new_body = section_to_body.get(sec.heading_text)
        if new_body is None or not sec.body_indices:
            continue

        body_elems = [paragraphs[i] for i in sec.body_indices]
        first_body_elem = body_elems[0]

        local_templates: dict[str, etree._Element] = {}
        local_default: Optional[etree._Element] = None
        if marker_templates is None and default_template is None:
            local_templates, local_default = _build_template_library(body_elems)

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
            key = marker if marker else "__plain__"
            tpl_src = (
                (marker_templates.get(key) if marker_templates else None)
                or (marker_templates.get("__plain__") if marker_templates else None)
                or default_template
                or local_templates.get(marker)
                or local_templates.get("")
                or local_default
            )
            if tpl_src is None:
                continue
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


def _pick_canonical_templates_by_marker(
    all_section_xmls: list[Path],
) -> tuple[dict[str, etree._Element], Optional[etree._Element]]:
    """
    문서 전체를 스캔해 각 머리 기호별로 '처음 나오는 본문 단락'을 캐노니컬 템플릿으로 채용.
    반환: ({marker: template_element}, 기본_템플릿)
    - 같은 기호는 문서 내에서 항상 동일 스타일로 렌더링
    - 기본 템플릿: 기호가 없는 라인에 사용 (첫 번째 일반 본문 단락)
    """
    by_marker: dict[str, etree._Element] = {}
    default: Optional[etree._Element] = None
    for sx in all_section_xmls:
        _, paragraphs, sections = parse_sections(sx)
        for sec in sections:
            for idx in sec.body_indices:
                p = paragraphs[idx]
                txt = _paragraph_text(p)
                if not txt:
                    continue
                m = _line_marker(txt)
                key = m if m else "__plain__"
                if key not in by_marker:
                    cloned = _strip_and_clear(etree.fromstring(etree.tostring(p)))
                    if cloned is not None:
                        by_marker[key] = cloned
                        if default is None:
                            default = cloned
    return by_marker, default


def _strip_auto_numbering(p: etree._Element) -> None:
    """
    자동 번호 매기기 (paraPrIDRef, styleIDRef 가 가리키는 '가.나.다…' 스타일) 해제.
    단락 내부의 번호 관련 <hp:numPr>, <hp:autoNumFormat> 도 제거.
    """
    for attr in ("paraPrIDRef", "styleIDRef"):
        if attr in p.attrib:
            del p.attrib[attr]
    for local in ("numPr", "autoNumFormat", "numbering", "listLevel"):
        for el in p.iter():
            if etree.QName(el).localname == local:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
                break


def _strip_and_clear(p: Optional[etree._Element]) -> Optional[etree._Element]:
    if p is None:
        return None
    _strip_layout_cache(p)
    _strip_auto_numbering(p)
    for t in p.xpath(".//hp:t", namespaces=NS):
        t.text = ""
    return p


def _find_heading_index(root: etree._Element, start: int = 0) -> Optional[int]:
    """루트의 직계 자식 중 start 이후 첫 헤딩 단락의 인덱스를 찾는다 (표 내부 제외)."""
    children = list(root)
    for i in range(start, len(children)):
        elem = children[i]
        if etree.QName(elem).localname != "p":
            continue
        if _is_inside_table(elem):
            continue
        txt = _paragraph_text(elem)
        if txt and _is_heading(txt):
            return i
    return None


SAMPLE_META_KEYWORDS = ("문서 제목", "작성기관", "작성자", "작성일", "목차")


def _find_section_start_loose(root: etree._Element) -> Optional[int]:
    """
    양식 문서용 완화된 섹션 시작 감지.
    자동 번호(paraPrIDRef 기반)로 hp:t 에 '1.' 숫자가 없어도 찾을 수 있도록.

    우선순위:
    1. _is_heading 으로 엄격 매치
    2. 표지/작성자 메타 키워드 스킵 후, styleIDRef/paraPrIDRef 있는 짧은 단락 (30자 이하)
    """
    strict = _find_heading_index(root, 0)
    if strict is not None:
        return strict

    children = list(root)
    for i, elem in enumerate(children):
        if etree.QName(elem).localname != "p":
            continue
        if _is_inside_table(elem):
            continue
        txt = _paragraph_text(elem)
        if not txt:
            continue
        if any(kw in txt for kw in SAMPLE_META_KEYWORDS):
            continue
        if len(txt) > 30:
            continue
        if "paraPrIDRef" in elem.attrib or "styleIDRef" in elem.attrib:
            return i
    return None


def _find_next_section_start_loose(
    root: etree._Element,
    start: int,
    first_heading_level: Optional[int] = None,
) -> Optional[int]:
    """
    양식 내 '다음 섹션 시작' 감지. first 헤딩 레벨보다 깊은 sub-heading(가./A./(1)) 은
    같은 섹션 본문으로 취급하고, 같은 레벨 이상의 헤딩만 다음 섹션 경계로 사용.
    """
    children = list(root)
    for i in range(start, len(children)):
        elem = children[i]
        if etree.QName(elem).localname != "p":
            continue
        if _is_inside_table(elem):
            continue
        txt = _paragraph_text(elem)
        if txt and _is_heading(txt):
            lvl = _heading_level(txt)
            if first_heading_level is None or lvl <= first_heading_level:
                return i
    return None


def _clone_block(elements: list[etree._Element]) -> list[etree._Element]:
    return [etree.fromstring(etree.tostring(e)) for e in elements]


def _strip_tables_from_block(cloned: list[etree._Element]) -> list[etree._Element]:
    """
    복제된 블록에서 표(<hp:tbl>), 표만 포함한 단락, 완전히 빈 단락을 제거.
    양식의 샘플 표와 빈 줄(공간)이 섹션 수만큼 반복 복제되는 것 방지.
    """
    PIC_LOCALS = {"pic", "container", "rect", "line", "lineShape", "recShape"}
    result: list[etree._Element] = []
    for elem in cloned:
        if etree.QName(elem).localname == "tbl":
            continue
        for tbl in list(elem.iter()):
            if etree.QName(tbl).localname == "tbl":
                parent = tbl.getparent()
                if parent is not None:
                    parent.remove(tbl)
        if etree.QName(elem).localname == "p":
            txt = _paragraph_text(elem)
            has_visual = any(etree.QName(e).localname in PIC_LOCALS for e in elem.iter())
            # 텍스트도 없고 그림/도형도 없으면 완전 빈 단락 → 제거
            if not txt and not has_visual:
                continue
        result.append(elem)
    return result


def render_with_baseline_layout(
    sample_hwpx: str,
    headings: list[str],
    heading_to_body: dict[str, str],
    output_hwpx: str,
) -> dict:
    """
    양식 문서를 베이스라인으로 사용해 헤딩 N개짜리 결과 HWPX 생성.

    양식의 첫 번째 헤딩 ~ 다음 헤딩 직전(또는 문서 끝) 까지를 '섹션 블록'으로 식별.
    이 블록을 headings 리스트 수만큼 복제하고, 각 복제본의:
      - 헤딩 단락 텍스트 → headings[i]
      - 본문 단락 텍스트 → heading_to_body[headings[i]] 의 줄 단위
      - 표·캡션·이미지 등 그 외 요소는 양식 그대로 유지 (placeholder 역할)

    양식의 표지/헤더/작성자/푸터(첫 헤딩 이전) 는 건드리지 않음.
    """
    import copy
    import tempfile
    import zipfile

    if not Path(sample_hwpx).exists():
        raise FileNotFoundError(sample_hwpx)

    with tempfile.TemporaryDirectory() as tmp:
        _extract(sample_hwpx, tmp)
        section_xmls = _find_all_section_xmls(tmp)

        target_xml: Optional[Path] = None
        first_idx: Optional[int] = None
        for sx in section_xmls:
            tree = etree.parse(str(sx))
            root = tree.getroot()
            idx = _find_section_start_loose(root)
            if idx is not None:
                target_xml = sx
                first_idx = idx
                break

        if target_xml is None or first_idx is None:
            raise RuntimeError("양식 문서에서 섹션 시작점을 찾을 수 없음. 헤딩이나 스타일이 지정된 짧은 단락이 필요.")

        tree = etree.parse(str(target_xml))
        root = tree.getroot()
        children = list(root)

        first_heading_text = _paragraph_text(children[first_idx])
        first_heading_level = _heading_level(first_heading_text) if _is_heading(first_heading_text) else None
        next_idx = _find_next_section_start_loose(root, first_idx + 1, first_heading_level)
        end_idx = next_idx if next_idx is not None else len(children)

        template_block = children[first_idx:end_idx]

        # 원본 블록을 루트에서 제거 (insert_pos 유지)
        for elem in template_block:
            root.remove(elem)

        # 양식 템플릿에서 마커별 대표 단락 추출 (첫 헤딩 제외)
        marker_pool: dict[str, etree._Element] = {}
        for el in template_block[1:]:
            if etree.QName(el).localname != "p":
                continue
            if _is_inside_table(el):
                continue
            txt = _paragraph_text(el)
            if not txt:
                continue
            key = _classify_line_marker(txt)
            if key not in marker_pool:
                marker_pool[key] = el
        fallback_body = template_block[-1] if template_block else None

        insert_pos = first_idx
        for heading_text in headings:
            heading_clone = etree.fromstring(etree.tostring(template_block[0]))
            _strip_layout_cache(heading_clone)
            _strip_auto_numbering(heading_clone)
            _set_paragraph_text(heading_clone, heading_text)

            body_text = heading_to_body.get(heading_text, "").strip()
            body_lines = [ln for ln in body_text.split("\n") if ln.strip()]

            section_elems: list[etree._Element] = [heading_clone]
            for line in body_lines:
                key = _classify_line_marker(line)
                src = marker_pool.get(key)
                if src is None:
                    src = marker_pool.get("PLAIN")
                if src is None:
                    src = fallback_body
                if src is None:
                    continue
                new_p = etree.fromstring(etree.tostring(src))
                _strip_layout_cache(new_p)
                _set_paragraph_text(new_p, line)
                section_elems.append(new_p)

            section_elems = _strip_tables_from_block(section_elems)

            for offset, elem in enumerate(section_elems):
                root.insert(insert_pos + offset, elem)
            insert_pos += len(section_elems)

        tree.write(str(target_xml), xml_declaration=True, encoding="UTF-8", standalone=True)
        _repack(tmp, output_hwpx)

    size = Path(output_hwpx).stat().st_size
    return {
        "path": output_hwpx,
        "bytes": size,
        "sections_generated": len(headings),
        "block_size": len(template_block),
    }


def render_from_template(
    template_hwpx: str,
    section_to_body: dict[str, str],
    output_hwpx: str,
    style_source_hwpx: Optional[str] = None,
) -> dict:
    """
    템플릿 HWPX를 열어 모든 section XML을 순회하며 매칭되는 섹션 본문을 교체.
    기호별(○/-/△/…) 문서 전체에 통일된 스타일.

    style_source_hwpx 지정 시: 본문 단락 스타일(글자/문단)을 이 파일에서 가져옴.
      - 글쓰기 주입 대상은 template_hwpx (구조·표지·표 유지)
      - 디자인은 style_source_hwpx (깨끗한 본문 서식 차용)
    """
    replaced = 0
    with tempfile.TemporaryDirectory() as tmp:
        _extract(template_hwpx, tmp)
        section_xmls = _find_all_section_xmls(tmp)

        if style_source_hwpx and Path(style_source_hwpx).exists():
            with tempfile.TemporaryDirectory() as style_tmp:
                _extract(style_source_hwpx, style_tmp)
                style_section_xmls = _find_all_section_xmls(style_tmp)
                marker_templates, default_template = _pick_canonical_templates_by_marker(style_section_xmls)
        else:
            marker_templates, default_template = _pick_canonical_templates_by_marker(section_xmls)

        for section_xml in section_xmls:
            _, _, sections = parse_sections(section_xml)
            matching = {s.heading_text: section_to_body[s.heading_text] for s in sections if s.heading_text in section_to_body}
            if not matching:
                continue
            inject_section_body(
                section_xml,
                matching,
                marker_templates=marker_templates,
                default_template=default_template,
            )
            replaced += len(matching)
        _repack(tmp, output_hwpx)
    size = Path(output_hwpx).stat().st_size
    return {"path": output_hwpx, "bytes": size, "sections_replaced": replaced}
