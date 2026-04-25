from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from .md_parser import Document
from .slide_scanner import SlotCatalog, TableSlot, TextSlot


@dataclass
class TableAssignment:
    md_table_idx: int
    slot: TableSlot
    score: float
    col_map: list[Optional[int]]  # md_col_idx → template_col_idx (or None to skip)


@dataclass
class TextAssignment:
    role: str                     # "title" | "subtitle" | "footer"
    text: str
    slot: TextSlot
    score: float


@dataclass
class HeadingPlan:
    """A markdown H2 rendered as a section-divider slide.

    - If `is_duplicate` is False, the exemplar slide at `source_slide_idx` is
      edited in place: its title text is replaced with `text`.
    - If `is_duplicate` is True, a copy of that slide is made first, and the
      copy's title is edited. The source slide stays untouched.

    `table_ref` (optional) is the index into Plan.tables that belongs under this
    heading; used only to compute final slide ordering.
    """
    text: str
    source_slide_idx: int
    is_duplicate: bool
    table_ref: Optional[int] = None


@dataclass
class Plan:
    titles: list[TextAssignment]
    tables: list[TableAssignment]
    headings: list[HeadingPlan] = field(default_factory=list)
    unmatched_tables: list[int] = field(default_factory=list)

    def used_slide_indices(self) -> set[int]:
        used: set[int] = set()
        for t in self.titles:
            used.add(t.slot.slide_idx)
        for t in self.tables:
            used.add(t.slot.slide_idx)
        for h in self.headings:
            if not h.is_duplicate:
                used.add(h.source_slide_idx)
        return used


TABLE_MATCH_THRESHOLD = 0.55
COL_MATCH_THRESHOLD = 0.50


def _headers_score(md_headers: list[str], tpl_headers: list[str]) -> float:
    md_join = " ".join(h for h in md_headers if h)
    tpl_join = " ".join(h for h in tpl_headers if h)
    if not md_join or not tpl_join:
        return 0.0
    return fuzz.token_set_ratio(md_join, tpl_join) / 100.0


def _build_col_map(md_headers: list[str], tpl_headers: list[str]) -> list[Optional[int]]:
    used: set[int] = set()
    col_map: list[Optional[int]] = [None] * len(md_headers)

    for mi, md_h in enumerate(md_headers):
        if not md_h:
            continue
        best_idx: Optional[int] = None
        best_score = 0.0
        for i, tpl_h in enumerate(tpl_headers):
            if i in used or not tpl_h:
                continue
            score = fuzz.ratio(md_h, tpl_h) / 100.0
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is not None and best_score >= COL_MATCH_THRESHOLD:
            col_map[mi] = best_idx
            used.add(best_idx)

    for mi in range(len(md_headers)):
        if col_map[mi] is not None:
            continue
        if mi < len(tpl_headers) and mi not in used and not tpl_headers[mi]:
            col_map[mi] = mi
            used.add(mi)
            continue
        empty_candidates = [
            i for i, h in enumerate(tpl_headers) if not h and i not in used
        ]
        if empty_candidates:
            nearest = min(empty_candidates, key=lambda i: abs(i - mi))
            col_map[mi] = nearest
            used.add(nearest)

    if all(c is None for c in col_map) and tpl_headers:
        col_map = [i if i < len(tpl_headers) else None for i in range(len(md_headers))]
    return col_map


def _pick_text_slot(
    role: str,
    needle: str,
    catalog: SlotCatalog,
    used: set[int],
) -> TextAssignment | None:
    best: tuple[float, int, TextSlot] | None = None
    for i, slot in enumerate(catalog.text_slots):
        if i in used:
            continue
        score = fuzz.token_set_ratio(needle, slot.text) / 100.0 if slot.text else 0.0
        if role == "title":
            if slot.slide_idx in (1, 3) and len(slot.text) < 80:
                score += 0.2
        elif role == "subtitle":
            # 제목 슬라이드의 부제 휴리스틱: 연도·직위·기관 키워드 포함 시 가산점
            if any(k in slot.text for k in ("20", "Prof", "Dr", "기관", "주관")):
                score += 0.15
            if slot.slide_idx in (1, 13):
                score += 0.1
        elif role == "footer":
            if slot.slide_idx in (1, 13):
                score += 0.2
        if best is None or score > best[0]:
            best = (score, i, slot)
    if best is None or best[0] < 0.2:
        return None
    return TextAssignment(role=role, text=needle, slot=best[2], score=best[0])


def _find_section_exemplar(catalog: SlotCatalog) -> int | None:
    """Pick the slide that looks most like a section-divider template.

    Heuristic: a slide with exactly one short text slot (title-like) and no tables.
    Ties broken by shortest text length (cleaner divider).
    """
    by_slide_text: dict[int, list[TextSlot]] = {}
    for slot in catalog.text_slots:
        by_slide_text.setdefault(slot.slide_idx, []).append(slot)
    slides_with_tables = {ts.slide_idx for ts in catalog.table_slots}

    best_idx: int | None = None
    best_score = -1.0
    for slide_idx, slots in by_slide_text.items():
        if slide_idx in slides_with_tables:
            continue
        if len(slots) != 1:
            continue
        txt = slots[0].text or ""
        if len(txt) > 120:
            continue
        score = 0.5
        # Prefer divider-ish text like "Part I. …".
        if txt.startswith("Part ") or " Part " in txt:
            score += 0.4
        # Short titles are better exemplars.
        score += max(0.0, (100 - len(txt)) / 500.0)
        if score > best_score:
            best_score = score
            best_idx = slide_idx
    return best_idx


def _find_title_slot_on_slide(
    catalog: SlotCatalog, slide_idx: int, used: set[int]
) -> tuple[int, TextSlot] | None:
    """Pick the best 'title' text slot on a given slide.

    Heuristic: shortest-text slot among unused slots on that slide. This matches
    the convention that slide titles are shorter than body text.
    """
    candidates = [
        (i, slot)
        for i, slot in enumerate(catalog.text_slots)
        if slot.slide_idx == slide_idx and i not in used
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: len(p[1].text or ""))
    return candidates[0]


def build_plan(doc: Document, catalog: SlotCatalog) -> Plan:
    plan = Plan(titles=[], tables=[])
    used_text: set[int] = set()

    # 1) Title, subtitle, footer → best text slots (existing behavior).
    for role, content in (("title", doc.title), ("subtitle", doc.subtitle), ("footer", doc.footer)):
        if not content:
            continue
        asn = _pick_text_slot(role, content, catalog, used_text)
        if asn:
            plan.titles.append(asn)
            used_text.add(catalog.text_slots.index(asn.slot))

    # 2) Match tables by header Jaccard.
    used_tbl: set[int] = set()
    for ti, table in enumerate(doc.tables):
        best_idx: int | None = None
        best_score = 0.0
        for si, slot in enumerate(catalog.table_slots):
            if si in used_tbl:
                continue
            s = _headers_score(table.headers, slot.headers)
            if s > best_score:
                best_score = s
                best_idx = si
        if best_idx is not None and best_score >= TABLE_MATCH_THRESHOLD:
            slot = catalog.table_slots[best_idx]
            col_map = _build_col_map(table.headers, slot.headers)
            plan.tables.append(
                TableAssignment(md_table_idx=ti, slot=slot, score=best_score, col_map=col_map)
            )
            used_tbl.add(best_idx)
        else:
            plan.unmatched_tables.append(ti)

    # 3) Headings (H2) → section-divider slides.
    # Each H2 becomes a dedicated section slide, duplicated from an exemplar.
    exemplar = _find_section_exemplar(catalog)
    if exemplar is not None:
        first_use = True
        for heading in doc.headings:
            plan.headings.append(
                HeadingPlan(
                    text=heading,
                    source_slide_idx=exemplar,
                    is_duplicate=not first_use,
                )
            )
            first_use = False

    return plan


def format_plan(plan: Plan, doc: Document) -> str:
    lines = ["# md2pptx — mapping plan", ""]
    lines.append("## Text slots")
    if not plan.titles:
        lines.append("  (none)")
    for a in plan.titles:
        lines.append(
            f"  [{a.role:>8}]  slide {a.slot.slide_idx:2d}  score={a.score:.2f}  "
            f"→ {a.text[:60]!r}"
        )
    lines.append("")
    lines.append("## Section headings (H2)")
    if not plan.headings:
        lines.append("  (none)")
    for h in plan.headings:
        kind = "duplicate" if h.is_duplicate else "reuse"
        lines.append(
            f"  [{kind:>9}]  from slide {h.source_slide_idx:2d}  "
            f"→ {h.text[:60]!r}"
        )
    lines.append("")
    lines.append("## Tables")
    if not plan.tables and not plan.unmatched_tables:
        lines.append("  (none)")
    for a in plan.tables:
        md_t = doc.tables[a.md_table_idx]
        lines.append(
            f"  MD[{a.md_table_idx}] ({md_t.nrows}x{md_t.ncols}) "
            f"→ slide {a.slot.slide_idx:2d} table ({a.slot.n_rows}x{a.slot.n_cols})  "
            f"score={a.score:.2f}"
        )
        lines.append(f"    col_map: {a.col_map}")
        lines.append(f"    md headers: {md_t.headers}")
        lines.append(f"    tpl headers: {a.slot.headers}")
    for ti in plan.unmatched_tables:
        md_t = doc.tables[ti]
        lines.append(
            f"  MD[{ti}] ({md_t.nrows}x{md_t.ncols}) → NO MATCH (headers={md_t.headers})"
        )
    return "\n".join(lines)
