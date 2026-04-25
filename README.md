# gemma-docu-writer

로컬 PC 에서 동작하는 React + FastAPI 웹앱. 여러 소스 문서(HWP/HWPX/PDF/MD)를 세 가지 경로로 완성 문서로 변환:

1. **한글 HWPX** — 비전 기반 스타일 추출 + LLM 본문 합성 (Ollama / Gemini)
2. **PPTX (표 중심)** — 기존 양식 PPTX 에 MD 헤딩·표를 주입. 결정론적·byte-level 디자인 보존
3. **PPTX (줄글 중심)** — MD 의 줄글·bullet 단락을 양식의 본문 shape 에 자동 주입

> 상세 설명: [docs/README.md](docs/README.md) · [docs/hwpx-vision-mcp.md](docs/hwpx-vision-mcp.md) · [docs/pptx-md2pptx.md](docs/pptx-md2pptx.md) · 샘플: [docs/examples/prose_example.md](docs/examples/prose_example.md)

## 세 가지 변환 경로 비교

| 경로 | 엔진 | 입력 MD 특징 | 양식 요구사항 | 외부 API |
|------|------|------------|-------------|---------|
| **① HWPX** | hwpx_vision + LLM | H1/H2/H3 구조 + 본문 | HWPX 참조 문서 1개 | Ollama 또는 Gemini (선택) |
| **② PPTX 표 중심** | md2pptx (결정론) | `# Title` + `## Section` + 마크다운 표 | 양식 PPTX (표 슬롯 포함) | **없음** |
| **③ PPTX 줄글 중심** | md2pptx + body_blocks | `## Section` + 줄글 단락·bullet | 양식에 **본문용 placeholder shape** 필요 | **없음** |

---

## 공통 흐름

```
         원본 HWP/PDF ──(kordoc)──▶ 여러 MD
                                      │
                                      ▼
                          📝 MD 합성 (HWPX 탭)
                          여러 MD → 통합 MD 한 개
                                      │
                                 통합 MD 한 개
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
                 ▼                                         ▼
      ✍ 슬라이드 글쓰기 (PPTX 탭)                     🎯 HWPX 생성
     (양식 구조 반영 MD 재구조화, 선택)           (비전 + LLM 본문)
                 │                                         ▼
                 ▼                                     결과 HWPX
          🎨 PPTX 변환
        (md2pptx 결정론)
                 │
                 ▼
           결과 PPTX
                 │
        ─── 이상 감지 ───
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   (A) 🔧 MD 개선       (B) 사용자 수기 수정
   LLM refiner           양식 PPTX 편집 후 재업로드
   MD 재작성 제안
        │                 │
        └────────┬────────┘
                 │
                 ▼
           재변환 (🎨 PPTX)
```

- **📝 MD 합성 (HWPX 탭)** — 여러 원본 MD 를 LLM 으로 하나로 합쳐 통합 MD 생성. 결과 MD 는 HWPX·PPTX 양쪽 모두에 사용 가능.
- **✍ 슬라이드 글쓰기 (PPTX 탭)** — 변환 **전** 예방 단계. 양식 PPTX 구조(슬라이드 수·표 행수·본문 용량)를 LLM 에게 알려주고 MD 를 재구조화. 긴 표는 미리 분할, 줄글은 bullet 으로 요약. **이미 슬라이드용 MD 면 건너뛰어도 OK** — 바로 `🚀 변환 시작` 으로.
- **🎨 PPTX 변환** — 결정론적 md2pptx 엔진으로 즉시 변환.
- **이상 감지 시 피드백 루프는 두 갈래** (변환 **후** 보정):
  - **(A) LLM refiner 경로** — `🔧 결과 분석하고 MD 개선 제안 받기` 버튼. analyzer 가 표 넘침·셀 클리핑·미매칭·prose 매핑 실패 등을 감지하면 LLM 이 MD 수정안을 diff 로 제안 → 사용자 승인 → 재변환.
  - **(B) 사용자 수기 수정 경로** — 양식 PPTX 를 직접 편집(행 추가, shape 제거, 폰트 조정 등) 해서 재업로드 → 재변환.
- **예방(✍) vs 사후대응(🔧) 2단계 방어**. 두 경로 모두 **사람이 제어** (자동 무한 루프 없음).

---

## 공통 설치·실행

```bat
install.bat   # 최초 1회 — Python venv, npm install
start.bat     # 백엔드(8765) + 프론트(5173) 동시 기동 + 브라우저 오픈
```

사전 요구사항:

| 항목 | 용도 | 필수 여부 |
|------|------|---------|
| Python 3.11+ | 백엔드 / 변환 엔진 | 모든 경로 필수 |
| Node 18+ | 프론트엔드 | 모든 경로 필수 |
| **Ollama + qwen2.5:3b** | 로컬 텍스트 LLM (가벼움, ~2GB) | 클라우드 안 쓸 때 권장. `install.bat` 가 자동 pull |
| Gemini API 키 | 클라우드 LLM (텍스트 + HWPX 비전) | HWPX 비전 분석 시 필수 (qwen2.5 는 비전 없음) |
| LibreOffice | HWP → 이미지 변환 | 경로 ① HWPX (HWP 참조 문서 쓸 때) |
| kordoc | HWP → MD 변환 | 선택 (PDF/HWPX 는 자동 폴백) |

> **로컬 LLM 모델 선택**: `qwen2.5:3b` 가 RAM 4-8GB 노트북 기본. 더 좋은 PC 면 Settings 모달에서 `qwen2.5:7b` (RAM 8-16GB), `mistral:7b`, `gemma2:9b` (RAM 16GB+), `gemma3:4b` (로컬 비전) 등 선택 가능. 직접 입력도 지원.

**경로 ② / ③ PPTX 는 LLM 없어도 동작** — `install.bat` 의 Python · Node 만 있으면 됨.

---

## 경로 ① — 한글 HWPX 결과보고서

**용도**: 한국어 공공·행정 결과보고서 생성. 참조 HWPX 한 개를 보고 헤딩 체계 · 폰트 · 여백을 학습한 뒤, 여러 MD 소스를 하나로 합성해 본문 생성.

**입력**:
- 계획서 HWP/HWPX/PDF (스타일 참조 + 본문 구조)
- 추가 MD 파일 여러 개 (Work Plan, Wrap Up 등)

**출력**: 참조와 동일한 양식의 결과보고서 HWPX

**사용 순서**:
1. 🎯 HWPX 탭 진입
2. 원본 HWP/PDF 우클릭 → "MD 로 변환" (kordoc 필요 시 자동 폴백)
3. 참조 양식 HWPX 우클릭 → "🎯 글쓰기 주입 문서로 지정" 또는 "📐 양식 문서로 지정"
4. 소스 MD 들 Ctrl+클릭 다중 선택
5. 상단 **📝 MD 합성** → 양식 헤딩 구조를 따른 결과보고서 MD 초안 자동 생성
6. 중앙에서 MD 검수 (외부 에디터 수정 후 ⟳ 로 새로고침)
7. **🎯 HWPX 생성** → `*_YYYYMMDD_HHmm.hwpx`

상세: [docs/hwpx-vision-mcp.md](docs/hwpx-vision-mcp.md)

---

## 경로 ② — PPTX 표 중심 변환

**용도**: 이미 표·셀 구조가 확정된 MD (출장 일정표, 성과 평가표 등) 를 기관 공식 양식 PPTX 에 주입.

**입력**:
- MD 파일 (H1/H2 + 마크다운 표 포함)
- 양식 PPTX (표 슬롯 + section-divider 슬라이드 포함)

**출력**: 양식 디자인 그대로, 표 내용만 MD 로 교체된 PPTX

**양식 PPTX 조건**:
- 매칭 대상 표 슬롯이 **헤더 행을 명시적으로 포함** (MD 표 헤더와 token similarity ≥ 0.55 이면 매칭)
- section-divider 슬라이드 (짧은 제목 1개만 있는 슬라이드) 1장 이상 필요 — H2 개수만큼 자동 복제
- 로고·이미지·장식 shape 은 어디에 있어도 보존

**사용 순서**:
1. 🎨 PPTX 탭 진입
2. 탐색기에서 MD 클릭 → 카드 MD 칸에 자동 등록
3. 양식 PPTX 클릭 → 카드 PPTX 칸에 자동 등록
4. (선택) MD 가 복잡하면 **✍ 양식에 맞게 MD 재작성** — LLM 이 표 행수·슬라이드 수 맞춰 사전 정리
5. **🚀 변환 시작** → 같은 폴더에 `{md이름}_result_{ts}.pptx` 생성
6. (선택) 결과 이상 시 **🔧 결과 분석하고 MD 개선 제안 받기** — LLM 이 표 분할·셀 요약 등을 사후 제안

상세: [docs/pptx-md2pptx.md](docs/pptx-md2pptx.md)

---

## 경로 ③ — PPTX 줄글 중심 변환 (prose body)

**용도**: 마크다운 표가 적거나 없고 **줄글 단락·bullet 리스트** 위주인 MD 를 발표용 슬라이드로. 중간보고·기획안 등.

**입력**:
- MD 파일 (`## 섹션` 아래 긴 줄글 단락 또는 `- bullet` 리스트)
- 양식 PPTX (**본문용 placeholder shape 필수** — 아래 조건 참조)

**출력**: 각 `##` 섹션당 한 슬라이드. 제목은 section-divider, 본문은 placeholder shape 에 주입.

**양식 PPTX 조건 (중요)**:
경로 ② 와 달리 **줄글을 받을 shape 이 양식에 실제로 있어야** 함. 현재 엔진은 다음 기준으로 body shape 을 탐지:

- 제목 슬롯(title placeholder · 짧은 텍스트) 아닌 text shape
- **기존 텍스트 길이 30자 초과** (template 에 더미 텍스트가 들어있어야 "이 자리는 본문용" 인식)

**양식 준비 방법** (최소 샘플):
1. PowerPoint 로 양식 열기
2. 본문이 들어갈 슬라이드 선택 (section-divider 다음 슬라이드 권장)
3. 텍스트 상자 삽입 → 아래와 같은 **긴 더미 텍스트** 입력:
   ```
   여기에 본문을 작성하세요. 이 영역은 MD 의 ## 섹션 아래 줄글 단락이 자동으로 들어갈 자리입니다.
   여러 문단이 있으면 줄바꿈으로 이어지고, bullet 리스트는 • 기호와 함께 출력됩니다.
   ```
4. 폰트·크기·색 조정 후 저장

이 더미 텍스트 shape 이 있으면 `_apply_body_blocks` 가 그 자리에 실제 MD 줄글을 주입하고 더미는 교체됨.

**사용 순서**: 경로 ② 와 **완전히 동일**. 🎨 PPTX 탭에서 줄글 MD + 본문 shape 포함 양식 PPTX → (선택) **✍ 양식에 맞게 MD 재작성** 으로 줄글을 bullet 으로 사전 정리 → 🚀 변환 시작. 결과에 `body_blocks_matched` 수가 0 보다 크면 줄글 주입 성공.

**예시 MD**: [docs/examples/prose_example.md](docs/examples/prose_example.md)

**확인 방법**:
- 변환 후 카드 결과 섹션에 "body_blocks_matched: N" 로그
- N == 0 이면 양식에 본문 shape 이 없다는 뜻 → 양식 수정 필요
- 🔧 개선 제안 을 눌러도 analyzer 가 `prose_unmapped` 로 알려줌

---

## Provider 전환 (경로 ① HWPX / MD 합성·✍ 슬라이드 글쓰기·🔧 리파이너만 해당)

⚙ 설정 → Provider: **Ollama** (로컬) 또는 **Gemini** (클라우드, 권장). Gemini 는 무료 API 키 필요 ([aistudio.google.com](https://aistudio.google.com)). 대외비 자료는 Ollama 를 쓰세요.

### 로컬 모델 선택 (PC 사양 기준)

설정 모달에서 텍스트 모델 프리셋 드롭다운으로 선택. 사양 가이드:

| 체급 | 모델 | RAM 권장 | 속도 (CPU) | 한국어 품질 | 추천 상황 |
|------|------|---------|----------|-----------|----------|
| 플라이급 ★ | **qwen2.5:3b** (~2GB) | 4-8GB | 빠름 (실시간) | 양호 | **해외 사업자 / 사양 불명 노트북 / 기본값** |
| 미들급 | qwen2.5:7b (~4-5GB) | 8-16GB | 보통 | 좋음 | 일반 업무용 데스크톱 |
| 미들급 | mistral:7b (~4-5GB) | 8GB | 보통 | 영문 우수, 한글 보통 | 영문 위주 작업 |
| 헤비급 | gemma2:9b (~5-6GB) | 16GB+ | 느림 | 좋음 | 데스크톱·고사양 |
| 헤비/멀티모달 | gemma3n:e4b (~5GB) | 16GB+ | 느림 | 좋음 + 비전 | 비전 분석 필요 시 |
| 가벼운 비전 | gemma3:4b (~3-4GB) | 8GB+ | 보통 + 비전 | 보통 | 로컬 비전 옵션 |

> **권장 시나리오**:
> - **클라우드 주력 (Gemini) + 로컬 비상**: provider 를 Gemini 로 두고 모델은 `qwen2.5:3b` — 평소 Gemini, 오프라인·키 만료 시 자동 폴백 가능
> - **완전 오프라인 / 대외비**: provider 를 Ollama 로, 사양 따라 위 표에서 선택
> - **HWPX 비전 분석**: qwen2.5 시리즈는 비전 미지원 → Gemini 권장. 로컬 원하면 `gemma3:4b` 또는 `gemma3n:e4b` 선택

`install.bat` 가 기본으로 `qwen2.5:3b` 자동 pull. 다른 모델은 `ollama pull <모델명>` 으로 직접 받으면 됨.

PPTX 경로 ② / ③ 의 **결정론 변환** 자체는 LLM 없이 동작 — provider 설정 무관. 단 ✍ 슬라이드 글쓰기·🔧 리파이너는 LLM 사용.

---

## 자주 묻는 트러블슈팅

- **PPTX 표가 매핑 안 됨**: MD 표 헤더와 양식 표 헤더 유사도 낮음. MD 헤더를 양식에 맞추거나 🔧 개선 제안으로 LLM 에게 맡김.
- **줄글이 슬라이드에 안 나타남**: 양식에 본문 shape 없음. 위 "양식 준비 방법" 참조해 더미 텍스트 shape 추가.
- **표가 너무 길어 잘림**: 🔧 개선 제안 → 리파이너가 표를 여러 H2 로 분할 제안. 엔진이 표 슬라이드도 자동 복제해서 수용.
- **Ollama 오프라인 배지**: `ollama serve` 확인 (HWPX·MD 합성만 영향).
- **HWP 렌더링 실패**: LibreOffice 미설치. 참조 문서를 PDF 로 변환 후 `_context/` 에 넣고 재시도.

---

## UI 팁

- 상단 탭 **📝 HWPX / 🎨 PPTX** 로 작업 전환 (localStorage 기억)
- 좌·우 패널 경계를 **드래그** 로 폭 조절 (긴 파일명 보기 편하게). 폭 설정은 브라우저에 저장
- 탐색기에서 파일 클릭하면 카드 slot 에 자동 등록 — 우클릭 메뉴 없이 빠르게

## 아키텍처

```
┌──────────────┐   HTTP   ┌──────────────┐           ┌────────────────────┐
│ React (5173) │ ───────> │ FastAPI(8765)│           │ 경로①: hwpx_vision │
└──────────────┘          │  /api/...    │ ────────> │  (비전 + LLM)       │
                          │              │           │                    │
                          │  composer    │           │ 경로②③: md2pptx    │
                          │  llm.py ───> │ Ollama    │  (결정론, lxml)     │
                          │  (HWPX 전용)  │ /Gemini   │  + analyzer/       │
                          │              │ ────────> │   md_refiner (LLM) │
                          └──────────────┘           └────────────────────┘
```

## 배포

`install.bat` + 소스만 GitHub 업로드. `backend/.venv`, `frontend/node_modules`, `_context/` 사용자 자료, 생성물 `*_result_*.pptx`, `*_suggested_*.md` 는 `.gitignore` 처리.
