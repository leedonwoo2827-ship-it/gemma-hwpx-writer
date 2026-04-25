# PPTX — md2pptx-template 기반 결정론적 템플릿 주입

> `doc_mcp/md2pptx/` 에 위치.
> 기관 공식 PPTX 양식의 **디자인·폰트·표 구조를 byte-level 로 보존**하면서 MD 내용을 주입하는 결정론적 변환기. LLM·API 불필요.

---

## 1. 이 파이프라인이 해결하는 문제

제안서·발표자료는 기관마다 **공식 PPTX 양식** 이 정해져 있다. 사업자는 이 양식을 다음 조건으로 다뤄야 한다:

- 발주사·수행사 로고, 색상, 그림자, 표 테두리 **1픽셀도 어긋나면 안 됨**
- 본문은 PowerPoint 에서 **직접 편집 가능** (이미지 렌더링 안 됨)
- 국문·영문 두 벌 생성 필요 시 각각 양식 파일이 다름
- MD 작성자가 슬라이드 개수를 기억할 필요 없음 — 양식에 N장 있어도 MD 가 요구하는 것만 남기고 나머지 삭제

v1~v4 에서 시도했던 **비전 기반 area_id 매핑 + LLM 본문 작성** 방식은 매핑 실패율이 높고 UI 복잡도가 커서 폐기. 대신 Anthropic 의 pptx 스킬이 쓰는 **unpack → edit XML → pack** 패턴을 차용했다.

---

## 2. 엔진: md2pptx-template

소스: 사용자가 별도 개발한 MIT 라이선스 레포 ([github/leedonwoo2827-ship-it/md2pptx-template](https://github.com/leedonwoo2827-ship-it/md2pptx-template)) 를 `doc_mcp/md2pptx/` 로 벤더링.

### 파이프라인

```
Template.pptx ──unpack──▶ _unpacked/ppt/slides/*.xml
       │
MD ────md_parser──▶ Document{title, subtitle, footer, headings, tables[]}
       │                                      │
       ▼                                      ▼
slide_scanner (XPath 로 <a:tbl>·<p:sp> 카탈로그)
       │
       ▼
mapper (rapidfuzz Jaccard 헤더 매칭 + 역할 휴리스틱)
       │
       ▼
editor (lxml):
  · 텍스트 슬롯 = 첫 run 의 rPr 보존, <a:t> 만 교체
  · 테이블 슬롯 = 본문 행 <a:tr> 을 딥카피로 복제, 셀 채움, 초과 행 삭제
       │
slide_duplicator  (H2 추가될 때마다 섹션 구분 슬라이드 복제)
slide_remover     (MD 내용이 매핑 안 된 원본 슬라이드 삭제)
       │
       ▼
pack ──▶ output.pptx   (디자인 100% 보존, 매핑된 셀만 변경)
```

### 매핑 규칙

| MD 요소 | 양식에서 찾는 기준 |
|---|---|
| `# Title` | 슬라이드 1 근처의 짧은 타이틀 텍스트 shape |
| `*italic*` 선두 단락 | 날짜·작성자 키워드가 있는 subtitle-like shape |
| `*Source: ...*` 말미 단락 | 마지막 슬라이드의 footer-like shape |
| `## Section` (H2) | "짧은 텍스트 1개" 인 구분 슬라이드(section-divider). **첫 H2 는 원본 사용, 이후 H2 는 해당 슬라이드 복제** |
| MD 표 | 헤더 token_set_ratio 가 가장 높은 양식 테이블. 비어있는 헤더 열은 위치 기반 폴백 |

---

## 3. 사용자 기준 입력·출력

### 입력
- **MD 파일**: 헤딩 · 표 · 인용 포함 일반 마크다운.
  - 단일 MD 를 직접 쓸 수도 있고, 여러 원본 MD (예: 계획서·Work Plan·Wrap Up) 를 **HWPX 탭의 📝 MD 합성 (LLM)** 로 미리 통합한 뒤 그 결과 MD 를 PPTX 변환의 입력으로 써도 된다. MD 합성은 HWPX·PPTX 공통 전처리.
- **양식 PPTX**: 기관 공식 템플릿. 최소 조건:
  - section-divider 스타일 슬라이드 1장 (짧은 텍스트 1개인 슬라이드 — H2 복제 원본)
  - 매핑 대상 테이블들의 **헤더가 MD 표 헤더와 유사** (token_set_ratio 매칭)

### 출력
- 입력 MD 와 같은 폴더에 `{md이름}_result_{timestamp}.pptx` 생성
- 디자인·폰트·색·로고·그림자·표 테두리 → 원본 byte-level 보존
- 변경된 건 오직: 매핑된 텍스트 run 과 테이블 본문 행

### 예시 (실측)

입력:
- 양식 PPTX (예: 14장 표지·구분·본문 슬라이드 포함)
- 단일 MD (2개 H2 섹션, 2개 표)

출력: 5장 (표지 + Part I 구분 + Part I 본문표 + Part II 구분 + Thank You)
- MD 에 안 쓰인 9장 자동 삭제
- 첫 번째 MD 표 → 양식 테이블 매칭 성공 (8행 × 5열)
- 두 번째 MD 표 → 헤더 스키마 불일치로 skip + 경고

---

## 4. 한계 · 알려진 제약

| 한계 | 원인 | 회피 |
|------|------|-----|
| 헤더 스키마 다르면 표 skip | 결정론 — LLM 없이 유사도만 | MD 헤더를 양식 헤더에 맞춤 / 양식에 맞는 열 추가 |
| 이미지·차트 MD 지원 X | PPTX 에 새 이미지 삽입은 범위 제외 | 양식에 이미 있는 이미지는 보존됨 |
| section-divider 슬라이드 필수 | H2 복제 원본 필요 | 양식에 1장 이상 포함 |
| Python ≥ 3.10 | 타입 힌트 문법 | 기본 요구사항과 동일 |

---

## 5. 코드 구조 (`doc_mcp/md2pptx/`)

```
doc_mcp/md2pptx/
├── __main__.py            python -m doc_mcp.md2pptx 진입
├── cli.py                 argparse CLI + convert() 프로그래매틱 API
├── pack.py                ZIP unpack / pack
├── md_parser.py           markdown-it-py → Document / Table 데이터클래스
├── slide_scanner.py       XPath 로 <a:tbl>·<p:sp> 카탈로그 생성
├── mapper.py              rapidfuzz 헤더 Jaccard + col_map 구성
├── editor.py              lxml: set_sp_text, fill_table (행 복제)
├── slide_duplicator.py    슬라이드 안전 복제 (XML+rels+ContentTypes+sldIdLst)
├── slide_remover.py       슬라이드 삭제 + orphan notesSlide 정리
└── qa.py                  (선택) markitdown placeholder 검사 + soffice PDF 내보내기
```

### Python API (FastAPI 에서 호출)

```python
from doc_mcp.md2pptx.cli import convert

result = convert(
    template="template.pptx",
    md="input.md",
    out="output.pptx",
    dry_run=False,
    keep_unused=False,
)
# {
#   "output_path": ..., "slides_count": 5,
#   "slides_final": [1, 3, 7, 14, 13],
#   "slides_dropped": [2, 4, 5, 6, 8, 9, 10, 11, 12],
#   "headings_matched": [...], "tables_matched": [...],
#   "tables_unmatched": [1], "plan_text": "..."
# }
```

---

## 6. 엔드포인트 · UI

### 백엔드: `POST /api/pptx/convert`
```json
{
  "template_pptx": "<경로>.pptx",
  "md_path": "<경로>.md",
  "output_pptx": null,
  "dry_run": false,
  "keep_unused": false
}
```
응답: 매핑 결과 + 출력 경로.

### 프론트: `🎨 PPTX 탭` → 단일 카드
1. 탐색기에서 `.md` 클릭 → 카드 MD 칸 자동 등록
2. 탐색기에서 `.pptx` 클릭 → 카드 PPTX 칸 자동 등록
3. `🚀 변환 시작` → 몇 초 후 결과 PPTX 탐색기에 표시
4. 카드 하단 결과 섹션: 슬라이드 수, 매칭 표, 삭제된 슬라이드, 미매칭 경고

옵션:
- **미매칭 슬라이드 유지** — MD 에 없는 원본 슬라이드를 안 지움 (기본 OFF)
- **미리보기만 (dry-run)** — 매핑 계획만 보고 파일 안 만듦

---

## 7. 왜 비전 안 쓰나

v3/v4 는 LLM 비전으로 shape 역할을 식별했다 ("이 shape 는 제목 / 이건 본문"). 하지만:
- **매핑 실패율 30~50%** — LLM 이 area_id 를 지어내거나 엉뚱한 shape 를 고름
- **비결정적** — 같은 입력으로 매번 다른 결과
- **느리고 비쌈** — 슬라이드당 비전 호출

md2pptx-template 은 이 모든 걸 **양식 자체의 구조** 로 해결한다. 양식이 충분히 "의미있게 설계" 되어 있으면 (헤더 있는 테이블, 짧은 타이틀 shape, section-divider 레이아웃) 결정론적 규칙만으로 정확히 매핑된다. 양식이 그 조건을 못 맞추면 사용자가 양식을 조금 고치는 게 LLM 매핑을 디버깅하는 것보다 빠르다.

---

## 8. 참고

- 상위 레포: [md2pptx-template](https://github.com/leedonwoo2827-ship-it/md2pptx-template) (MIT)
- 패턴 원전: [Anthropic skills/pptx](https://github.com/anthropics/skills/tree/main/skills/pptx)
- HWPX 파이프라인과의 차이: [README.md](README.md) 비교표 참조
