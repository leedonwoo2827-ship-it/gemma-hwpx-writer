# HWPX Vision MCP — 한글 보고서 양식 유지 설계 문서

> `doc_mcp/hwpx_vision/` 에 위치한 MCP 서버.
> 한국어 공공·행정 결과보고서의 **양식·번호체계·로고·페이지 레이아웃을 그대로 유지**하면서 본문만 LLM으로 재생성하는 것이 목적.

---

## 1. 해결하려는 문제

전형적인 "MD → HWPX 변환"은 한국어 공공문서에서 실패한다.

| 한국 공공문서 특성 | 일반 MD 변환의 한계 |
|-----------------|-------------------|
| 표지 박스(제목/기간/PM 명판) | MD에 개념 자체가 없음 |
| 목차 자동 생성 (`..... 페이지번호`) | Markdown TOC는 형식이 다름 |
| 헤더/푸터에 기관 로고 (발주사 + 수행사) | 이미지 삽입을 스타일 지정 못함 |
| 헤딩 번호체계 (`1. / 가. / A. / ○ / -`) | `#` `##` `###` 와 매핑 모호 |
| 복잡한 표 (인력 × 과업 상세) | GFM 표로 표현 불가 |
| 함초롬바탕 10pt + 특정 여백 | CSS가 없음 |

결론: **MD 하나만으로는 한국 보고서 양식을 재현할 수 없다.**

---

## 2. 두 가지 접근법

이 MCP는 **독립적인 두 경로**를 제공한다. 용도에 따라 선택.

### 경로 A — 비전 기반 스타일 추출 (`analyze_style_from_image` + `apply_style_to_md`)

```
참조 HWP/PDF ─► LibreOffice headless ─► PNG 페이지
                                            │
                                            ▼
                                   멀티모달 LLM (Gemma4n/Gemini)
                                            │
                                            ▼
                                     StyleJSON
                                    (헤딩/본문/표/여백 규칙)
                                            │
         MD ────────────────────────────────┴──► HWPX (blank + styles)
```

**강점**: 참조 문서가 **이미지만 있어도** 작동 (HWPX 없이 PDF만으로도 OK)
**약점**: 새 HWPX를 밑바닥부터 만들기 때문에 **로고/표지/헤더 재현 불가**
**용도**: 참조 양식의 "분위기"만 가져오고 싶을 때, 가벼운 변환

### 경로 B — 템플릿 주입 (`template_inject`)

```
참조 HWPX (파일 4) ── 복사 ──► 출력 HWPX
       │                          │
       │ ZIP 해제                  │ 본문 <hp:p> 교체
       ▼                          ▲
  section*.xml 파싱               │
       │                          │
       ▼                          │
  헤딩 추출 ──► 섹션별 LLM 호출 ──┘
```

**강점**: **표지·목차·헤더·로고·페이지번호 전부 보존**. 본문만 바뀜
**약점**: 참조 HWPX 파일이 **반드시 있어야** 함 (HWP는 한/글에서 HWPX로 저장 필요)
**용도**: 같은 양식 보고서를 반복 작성할 때 (이번 케이스)

---

## 3. 제공 도구 (MCP Tools)

### 3.1 `analyze_style_from_image(image_paths, use_cache=True, model=None)`

- **입력**: 참조 문서 페이지 PNG 경로 리스트 (보통 1~3장)
- **처리**: Ollama `POST /api/generate` 에 base64 이미지 + 프롬프트 → JSON 응답 → Pydantic 검증
- **출력**: `StyleJSON` (헤딩 레벨별 번호/폰트/정렬, 본문 스타일, 표 테두리, 페이지 여백)
- **캐시**: 같은 이미지 SHA-256 hash → `.style_cache/<hash>.json` 재사용
- **실패 폴백**: JSON 파싱 실패 시 [default_preset()](../doc_mcp/hwpx_vision/lib/style_schema.py#L45) 으로 자동 대체

**StyleJSON 스키마** ([style_schema.py](../doc_mcp/hwpx_vision/lib/style_schema.py)):
```python
class HeadingLevel:
    level: 1~6
    font_name: str          # "함초롬바탕"
    font_size_pt: float
    bold: bool
    alignment: "left"|"center"|"right"
    numbering: str | None   # 예: "제 {n} 장", "{n}.", "{n}.{m}"
    space_before/after_pt

class BodyStyle:
    font_name, font_size_pt, line_spacing, first_line_indent_pt

class TableStyle:
    border_width_pt, header_bg_hex, header_bold

class PageMargin:
    top/bottom/left/right_mm
```

### 3.2 `apply_style_to_md(md_path, output_hwpx, style_json=None)`

- **입력**: MD 파일 경로 + StyleJSON (없으면 기본 프리셋)
- **처리**:
  1. `markdown-it-py` 로 AST 파싱
  2. `python-hwpx` (`HwpxDocument.new()`) 로 blank HWPX 생성
  3. 헤딩/단락/목록/표를 순차 `add_paragraph`
  4. `clean_markdown` 으로 `**`, `##`, `---` 등 Markdown 마커 제거
- **출력**: `{path, bytes}`

### 3.3 `render_hwp_to_images(source_path, dpi=150, out_dir=None)`

- **입력**: HWP/HWPX/PDF 파일
- **처리**:
  - PDF → PyMuPDF로 직접 페이지 래스터화
  - HWP/HWPX → LibreOffice headless (`soffice --convert-to pdf`) → PyMuPDF
- **출력**: 페이지별 PNG 경로 리스트
- **선택 사유**: LibreOffice는 무료/크로스플랫폼. 한/글 COM(pyhwpx)은 라이선스 필요.

### 3.4 `template_inject(template_hwpx, section_to_body, output_hwpx)` *(경로 B)*

- **입력**: 참조 HWPX 경로 + `{heading_text: body_text}` 딕셔너리
- **처리** ([hwpx_template.py](../doc_mcp/hwpx_vision/lib/hwpx_template.py)):
  1. ZIP 해제 → `Contents/section*.xml` 모두 파싱 (여러 섹션 지원)
  2. 각 `<hp:p>` 의 텍스트를 모아 **헤딩 판별**
     - 패턴: `1. ...` `가. ...` `A. ...` `(1) ...`
     - 제외: 날짜 (`2025.04.09.`), TOC 페이지번호 꼬리
  3. `body_paragraphs >= 3` 인 섹션만 교체 대상 (TOC/표 셀 노이즈 제거)
  4. LLM에서 받은 본문 텍스트를 `clean_markdown` 후 줄 단위로 나눠 새 `<hp:p>` 생성
     - **`<hp:linesegarray>` (라인 배치 캐시) 자동 제거** — 안 제거하면 새 텍스트가 원본 위치에 겹쳐 그려짐
  5. 재압축 → 새 HWPX 저장

---

## 4. 섹션별 LLM 호출 (품질 개선)

[section_composer.py](../backend/services/section_composer.py) — 3문서를 한 번에 합성하면 Gemma가 일반론화하는 경향이 있어 **섹션별로 짧게 호출**.

```python
async def compose_section(section_title, plan_md, workplan_md, wrapup_md) -> str:
    prompt = f"""다음은 섹션 "{section_title}" 의 본문만 작성하는 작업입니다.
    ... 3개 원문 전체 컨텍스트 제공 ...
    섹션 본문(제목 제외, 불릿 기호 ○/- 허용):"""
    return await provider.generate_text(prompt, system=SECTION_SYSTEM)
```

**왜 더 잘 나오나?**
- 컨텍스트가 집중되어 LLM이 일반론 대신 해당 섹션에 맞는 실제 내용을 추출
- 섹션당 수백 토큰 정도만 생성 → 반복/환각 줄어듦
- 실패시 섹션 단위로만 재시도 가능

**비용**: 섹션 N개 × 1회 호출. 19 섹션이면 Gemma 15~20분, Gemini 1분 30초.

---

## 5. Markdown 정리 규칙 ([md_clean.py](../doc_mcp/hwpx_vision/lib/md_clean.py))

LLM이 시스템 프롬프트를 무시하고 Markdown을 뱉어내는 경우가 많아 후처리로 강제 정리.

| 입력 | 출력 |
|------|------|
| `**bold**` | `bold` (굵기 제거, 한/글에서 후편집) |
| `## 제목` | `제목` (평문 단락) |
| `--- / === / ***` (구분선) | 삭제 |
| `* 항목` | `○ 항목` (깊이 0) |
| `  * 항목` | `  - 항목` (깊이 1+) |
| ``` `code` ``` | `code` |
| ` ```블록``` ` 경계 | 삭제 (내용은 보존) |
| 연속 빈 줄 | 1줄로 압축 |

---

## 6. Provider 추상화 ([llm.py](../backend/services/llm.py))

```
           ┌─ OllamaProvider ── http://localhost:11434 (로컬)
LLMProvider├─ GeminiProvider ── googleapis.com (클라우드)
```

- `generate_text(prompt, system)` → async generator (토큰 스트리밍)
- `generate_vision(image_paths, prompt, system)` → 단회 응답
- 설정은 `~/.config/hwpx_writer/config.json` (`.gitignore` 처리)
- Gemini 선택 시 UI에 "**문서가 Google로 전송됨**" 경고 배너 강제 노출
- 모델명 자유 입력 + `datalist` 제안 + 실시간 `GET /v1beta/models` 조회

---

## 7. 현재 상태와 한계

### ✅ 작동하는 것
- HWPX ZIP 해제/파싱/재압축
- 헤딩 자동 감지 (4 레벨 + 날짜/TOC 필터)
- 섹션별 LLM 생성 + SSE 스트리밍 (`[1/19]` 형태 진행바)
- 라인 캐시 제거로 단락 겹침 방지
- Markdown 마커 자동 정리
- 스타일 캐시 (이미지 해시 기반 재사용)

### ⚠️ 알려진 한계
1. **표가 있는 섹션은 표가 사라짐** — 섹션 본문을 통째로 교체하기 때문. 표 유지 로직은 향후 과제
2. **헤딩 텍스트 정확 매칭 필요** — 원본 HWPX 헤딩 문자열을 그대로 LLM에 넘기고 응답 키로 사용. 공백/특수문자 차이에 민감
3. **중복 헤딩 처리 단순** — 같은 텍스트가 본문/표셀에 중복 등장하면 첫 번째만 교체
4. **python-hwpx blank 문서는 미니멀** — 경로 A(apply_style)로 만든 HWPX는 양식 거의 없음. 한/글 후편집 필요
5. **Gemma로 장문 합성은 일반론화** — 품질 필요하면 Gemini 권장 (설정 토글)

### 🔮 향후 개선 후보
- 표 내부 `<hp:tbl>` 인식 → 표는 보존하고 표 주변 텍스트만 교체
- 헤딩-본문 스타일 상속 개선 (`paraPrIDRef` 복제 정교화)
- 참조 문서 비전 분석으로 자동 StyleJSON 생성 (경로 A 완전 자동화)
- 이미지/로고 주입 (`BinData/` 디렉터리 조작)

---

## 8. 빠른 사용 예 (파이썬)

```python
from doc_mcp.hwpx_vision.tools.template_inject import list_headings, inject_to_template

# 1. 헤딩 미리보기
headings = list_headings("참조.hwpx")
for h in headings:
    if h["body_paragraphs"] >= 3:
        print(f"L{h['level']}", h["heading"])

# 2. 섹션별 본문 준비 (LLM 호출 결과)
section_to_body = {
    "가. 목적 수행": "○ 주요 행사 기획 참여\n- 준비위원회 회의 진행",
    "나. 주요 과업 내역": "○ 워크숍 운영\n...",
}

# 3. 주입
result = inject_to_template("참조.hwpx", section_to_body, "출력.hwpx")
print(f"{result['sections_replaced']} 섹션 교체, {result['bytes']} bytes")
```

---

## 9. 왜 이 구조인가 (설계 이유)

**질문: 왜 "MD → HWPX" 만 하지 않고 "템플릿 주입" 까지 만들었나?**

실험 결과 Gemma4n / Gemini 로 합성한 MD를 아무리 잘 HWPX로 변환해도 **한국 공공문서의 표지/목차/헤더를 재현할 수 없다**. 이는 LLM 품질 문제가 아니라 **포맷 표현력 문제**.

반대로, 이미 존재하는 HWPX(지난 차수 보고서 등)를 템플릿으로 두고 **본문만 LLM이 갈아끼우면** 양식 문제는 사라진다. 남는 건 LLM의 내용 품질뿐이고, 그건 모델 선택으로 해결 가능 (Gemma → Gemini).

결과적으로:
- **처음 만들 때**: 경로 A로 대충 뽑고 한/글에서 다듬어 "표준 템플릿" HWPX 완성
- **이후 반복 작성**: 경로 B로 본문만 교체 → 1~2분에 결과물

양식 재현 비용을 **1회로 제한**하는 구조.

---

## 참조 파일

- [doc_mcp/hwpx_vision/server.py](../doc_mcp/hwpx_vision/server.py) — FastMCP 엔트리
- [doc_mcp/hwpx_vision/lib/hwpx_template.py](../doc_mcp/hwpx_vision/lib/hwpx_template.py) — 경로 B 핵심
- [doc_mcp/hwpx_vision/lib/hwpx_writer.py](../doc_mcp/hwpx_vision/lib/hwpx_writer.py) — 경로 A 핵심
- [doc_mcp/hwpx_vision/lib/md_clean.py](../doc_mcp/hwpx_vision/lib/md_clean.py) — 후처리
- [doc_mcp/hwpx_vision/lib/style_schema.py](../doc_mcp/hwpx_vision/lib/style_schema.py) — StyleJSON
- [backend/services/section_composer.py](../backend/services/section_composer.py) — 섹션별 LLM 호출
- [backend/routes/hwpx.py](../backend/routes/hwpx.py) — `/api/template/inject` SSE 엔드포인트
