# HWPX 결과보고서 작성툴

로컬 PC에서 동작하는 React + FastAPI 웹앱. 계획서(HWP) + Work Plan(PDF) + Wrap Up(PDF)을 합성해 국문 결과보고서 HWPX를 생성한다. 비전 모델(Gemma3n)이 참조 문서의 헤딩/스타일을 추출해 MD에 적용하는 방식.

## 구성

- **frontend/** — Vite + React (포트 5173)
- **backend/** — FastAPI (포트 8765)
- **mcp/hwpx_vision/** — 비전 기반 HWPX MCP (analyze_style / apply_style / render_hwp)
- **_context/** — 입력 문서 (HWP/PDF)

## 사전 요구사항

| 항목 | 용도 | 설치 |
|------|------|------|
| Python 3.11+ | 백엔드/MCP | https://www.python.org |
| Node 18+ | 프론트엔드 | https://nodejs.org |
| Ollama | 로컬 LLM | https://ollama.com |
| `gemma3n:e4b` | 비전+텍스트 | `ollama pull gemma3n:e4b` |
| LibreOffice | HWP→이미지 (선택) | https://www.libreoffice.org |
| kordoc | HWP→MD (선택) | `mcp/kordoc` 에 체크아웃 후 `npm install && npm run build` |

> 사용자 환경에서 모델명이 `gemma4:e4b`로 표기되더라도 태그만 다를 뿐 동작은 동일하다. 설정 모달에서 모델 이름을 실제 `ollama list` 결과에 맞게 수정할 것.

## 설치

```bat
install.bat
```

## 실행

```bat
start.bat
```

브라우저에서 `http://localhost:5173` (같은 네트워크의 다른 기기는 `http://<이PC의IP>:5173`).

## 사용 흐름

1. **설정(⚙)** 에서 작업 폴더 확인, Provider 선택(Ollama 기본), 모델명 확인.
2. 좌측 탐색기에서 HWP/PDF **우클릭 → "MD로 변환"** (kordoc 필요; 미설치 시 PDF만 폴백 변환).
3. **외부에서 만든 MD**라면 좌측 상단 드롭존에 드래그앤드롭.
4. MD 3개를 **Ctrl+클릭**으로 선택: 계획서 MD, Work Plan MD, Wrap Up MD.
5. 상단 **"결과보고서 생성"** 버튼 → 우측에 스트리밍 출력 → `*결과보고서_v1.0.md` 생성.
6. 생성된 MD 선택 후 중앙 **"HWPX로 변환"** → `*결과보고서_v1.0.hwpx`.
7. 상단 **"⚡ 직통 MD→HWPX"** 는 어떤 MD든 즉시 HWPX로 변환 (합성 단계 스킵).

## Provider 전환

설정에서 **Ollama ↔ Gemini** 토글. Gemini는 무료 API 키 필요 (https://aistudio.google.com). 선택 시 "문서가 Google로 전송됨" 경고 배너가 표시된다. 대외비 자료는 Ollama 사용.

## 트러블슈팅

- **Ollama 오프라인 배지**: `ollama serve` 실행 확인.
- **`gemma3n:e4b` 없음**: `ollama pull gemma3n:e4b`.
- **HWP 렌더링 실패**: LibreOffice 미설치. 참조 문서를 PDF로 변환해 `_context/`에 넣고 다시 시도.
- **kordoc 없음**: PDF만 내부 변환 가능. HWP는 Claude Desktop 등 외부 도구로 MD를 만들어 드롭존에 업로드.
- **HWPX 변환 중 `python-hwpx` 오류**: `pip install --upgrade python-hwpx` 후 `install.bat` 재실행.
- **JSON 파싱 실패로 스타일 추출 실패**: 자동으로 기본 프리셋으로 폴백됨. 우측 로그에서 확인.

## 배포

- `install.bat` + 소스만 GitHub에 업로드.
- `backend/.venv`, `mcp/hwpx_vision/.venv`, `frontend/node_modules`, `mcp/kordoc/node_modules`, `.style_cache/`, `*.hwpx` 는 `.gitignore` 처리됨.
- LibreOffice/한컴글꼴/Ollama 모델은 용량 문제로 별도 배포 권장.

## 아키텍처

```
┌──────────────┐   HTTP   ┌──────────────┐  in-proc  ┌───────────────────┐
│ React (5173) │ ───────> │ FastAPI(8765)│ ────────> │ mcp/hwpx_vision   │
└──────────────┘          │  /api/...    │           │  analyze/apply/   │
                          │              │           │  render           │
                          │  composer    │  HTTP     │                   │
                          │  llm.py ───> │ Ollama    │ python-hwpx,      │
                          │              │ /Gemini   │ LibreOffice+PyMuPDF│
                          └──────────────┘           └───────────────────┘
```

## 한계

- Gemma3n E4B는 글자 크기 상대 비교/헤딩 계층 추출에는 쓸만하지만 폰트명/pt 정밀도는 낮다 → StyleJSON은 상대 규칙 + 프리셋 병합.
- 3문서 합성은 컨텍스트 한도 내 청크 후 단일 호출. 대용량 문서는 섹션별로 나눠서 생성 권장.
- "완전 자동"이 아닌 "초안 자동 + 사용자 후편집" 파이프라인으로 설계됨.
