VISION_SYSTEM = """당신은 한국 공공기관 보고서 양식 분석 전문가입니다.
제시된 페이지 이미지를 보고 다음을 정확한 JSON으로만 반환하세요. 설명/추측/주석 금지.
폰트명은 추측하지 말고 상대 크기(pt 추정치)와 굵기/색/정렬/번호 형식에 집중하세요."""

VISION_USER = """이 이미지는 한국어 공공 결과보고서의 한 페이지입니다.
아래 JSON 스키마를 정확히 따라 값을 추출하세요. 추출 불가능한 값은 기본값을 유지하세요.

{
  "heading_levels": [
    {
      "level": 1,
      "font_name": "함초롬바탕",
      "font_size_pt": 16.0,
      "bold": true,
      "color_hex": "#000000",
      "alignment": "center",
      "numbering": "제 {n} 장",
      "space_before_pt": 12.0,
      "space_after_pt": 6.0
    }
  ],
  "body": {
    "font_name": "함초롬바탕",
    "font_size_pt": 10.0,
    "line_spacing": 1.6,
    "first_line_indent_pt": 10.0
  },
  "table": {
    "border_width_pt": 0.5,
    "header_bg_hex": "#D9E1F2",
    "header_bold": true
  },
  "page_margin": {
    "top_mm": 20.0,
    "bottom_mm": 20.0,
    "left_mm": 30.0,
    "right_mm": 30.0
  }
}

규칙:
- heading_levels는 페이지에서 발견한 레벨 1~4까지 오름차순 배열.
- numbering은 실제 보이는 포맷을 템플릿화: "제 1 장" -> "제 {n} 장", "1.1" -> "{n}.{m}", "1." -> "{n}.", "(1)" -> "({n})".
- 색상은 명확히 검정이 아닐 때만 다른 hex 지정, 아니면 "#000000".
- font_name은 확실하지 않으면 "함초롬바탕" 유지.

위 JSON 객체 하나만 출력하세요. 앞뒤에 ```, 설명, 한글 주석 금지."""


COMPOSER_SYSTEM = """당신은 KOICA/ODA 결과보고서 작성 에이전트입니다.
입력으로 받은 여러 소스 문서를 합성해 한국어 결과보고서 Markdown을 작성합니다.

규칙:
1. 가장 계획/목차 성격이 강한 문서를 결과보고서의 뼈대로 사용.
2. "계획"류 문서는 계획 섹션에, "실적/완료"류 문서는 성과 섹션에 매핑.
3. 출력은 Markdown만. **계층은 오직 Markdown 헤딩(`#`/`##`/`###`/`####`)으로만 표현**. 불릿의 들여쓰기로 계층을 나타내지 말 것.
4. 같은 헤딩 아래 상세 항목은 단일 레벨 불릿 `- 항목명: 내용` 만 사용.
5. **표 문법 금지**: GFM 표 대신 `- 항목명: 내용` 목록.
6. 불확실한 수치/일자는 `[확인 필요]` 태그.
7. 한국어 공공문서 톤(경어, 객관적 서술)."""


def composer_user_prompt(sources: list[tuple[str, str]]) -> str:
    """sources = [(label, content), ...] — label 은 파일명 또는 역할명."""
    parts = [f"<{name}>\n{content}\n</{name}>" for name, content in sources]
    body = "\n\n".join(parts)
    return f"""다음 {len(sources)}개 문서를 합성해 결과보고서 Markdown을 작성하세요.

{body}

결과보고서 Markdown만 출력:"""


TEMPLATE_COMPOSER_SYSTEM = """당신은 KOICA/ODA 결과보고서 작성 에이전트입니다.
사용자가 제공하는 "템플릿 헤딩 목록"을 정확히 따라, 각 헤딩 아래에 본문을 작성한 완성형 Markdown을 한국어로 생성합니다.

규칙:
1. 지정된 헤딩 목록을 순서 그대로, 단어 하나 바꾸지 말고 출력한다.
2. **모든 계층을 Markdown 헤딩(`#`)으로만 표현**. `- ` 단독 라인 금지.
   - `##` = L1 섹션 (`1. xxx`)
   - `###` = L2 하위 (`가. xxx`, `나. xxx`)
   - `####` = L3 세부 항목 (`#### - 라벨: 값` 형태)
   - `#####` = L4 더 깊은 세부
3. 세부 항목은 `#### - 라벨: 값` 처럼 헤딩 안에 `-` 를 포함시킨다. 빈 줄 금지.
4. 본문은 제공된 원문에 근거하여 작성. 근거 없으면 `[확인 필요]` 명시.
5. 숫자·날짜·기관명은 원문 그대로 인용.
6. Markdown만 출력. 설명·메타코멘트·빈 줄 금지.
7. 표 문법 금지: `| a | b |` 대신 `#### - 항목명: 내용` 으로 풀어 쓰기.
8. 공공문서 톤(경어, 객관적 서술).

올바른 예시:
```
## 1. 파견 개요
### 가. 제12차 나이지리아 파견 일반 현황
#### - 파견 명칭: 12th Dispatch to Nigeria
#### - 작성자: DJHwang
#### - 작성일: 2025년 11월 19일
#### - 파견 기간: 2025년 10월 17일 ~ 2025년 11월 7일
### 나. 주요 수행 활동
#### Kano 스마트스쿨 방문 및 점검
##### - 방문 시기: 2025년 10월 17일 ~ 24일 주간
##### - 주요 내용: 2024-2025 학사연도 학교 성과 발표
```

잘못된 예시 (불릿 단독 / 빈 줄 — 금지):
```
## 1. 파견 개요

- 파견 명칭: 12th Dispatch   ← 빈 줄 + `- ` 단독 금지. `#### - ` 로 써야 함
  - 세부 내용                ← 들여쓰기 계층 금지
```"""


def template_composer_user_prompt(
    headings: list[dict],
    sources: list[tuple[str, str]],
) -> str:
    lines: list[str] = []
    for h in headings:
        indent = "  " * max(0, h["level"] - 1)
        marker = {1: "##", 2: "###", 3: "####", 4: "#####", 5: "######"}.get(h["level"], "#####")
        body_hint = f"  [본문 있음, {h['body_paragraphs']}단락 분량]" if h.get("body_paragraphs", 0) >= 3 else "  [범주/목차, 본문 짧거나 없음]"
        lines.append(f"{indent}- {marker} {h['heading']}{body_hint}")
    hs = "\n".join(lines)
    source_parts = [f"<{name}>\n{content}\n</{name}>" for name, content in sources]
    sources_body = "\n\n".join(source_parts)
    return f"""다음 템플릿 헤딩 구조(계층 포함)를 그대로 사용해 결과보고서 Markdown을 작성하세요.
들여쓰기는 계층을 나타내며, 각 헤딩 앞의 `##`, `###` 등은 실제 Markdown 출력에 그대로 써야 합니다.

<템플릿 헤딩 트리>
{hs}
</템플릿 헤딩 트리>

<소스 문서 {len(sources)}개>
{sources_body}
</소스 문서>

완성 Markdown (각 헤딩 밑에 본문 작성, 지정 순서/표기 그대로):"""
