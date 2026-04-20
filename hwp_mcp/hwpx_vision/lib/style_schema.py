from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class HeadingLevel(BaseModel):
    level: int = Field(ge=1, le=6)
    font_name: str = "함초롬바탕"
    font_size_pt: float = 12.0
    bold: bool = True
    color_hex: str = "#000000"
    alignment: Literal["left", "center", "right"] = "left"
    numbering: Optional[str] = None
    space_before_pt: float = 12.0
    space_after_pt: float = 6.0


class BodyStyle(BaseModel):
    font_name: str = "함초롬바탕"
    font_size_pt: float = 10.0
    line_spacing: float = 1.6
    first_line_indent_pt: float = 10.0


class TableStyle(BaseModel):
    border_width_pt: float = 0.5
    header_bg_hex: str = "#D9E1F2"
    header_bold: bool = True


class PageMargin(BaseModel):
    top_mm: float = 20.0
    bottom_mm: float = 20.0
    left_mm: float = 30.0
    right_mm: float = 30.0


class StyleJSON(BaseModel):
    heading_levels: list[HeadingLevel] = Field(default_factory=list)
    body: BodyStyle = Field(default_factory=BodyStyle)
    table: TableStyle = Field(default_factory=TableStyle)
    page_margin: PageMargin = Field(default_factory=PageMargin)
    source_image_hashes: list[str] = Field(default_factory=list)


def default_preset() -> StyleJSON:
    return StyleJSON(
        heading_levels=[
            HeadingLevel(level=1, font_size_pt=16, alignment="center", numbering="제 {n} 장"),
            HeadingLevel(level=2, font_size_pt=14, numbering="{n}."),
            HeadingLevel(level=3, font_size_pt=12, numbering="{n}.{m}"),
            HeadingLevel(level=4, font_size_pt=11, numbering="({n})"),
        ]
    )
