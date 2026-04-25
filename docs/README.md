# gemma-docu-writer — 문서 파이프라인 개요

한국어 공공·행정 결과보고서 작성을 위한 로컬 웹 도구. 한국어 HWPX 와 영문/국문 PPTX 제안서 두 가지 출력 형식을 각각의 특성에 맞는 **다른 파이프라인** 으로 처리한다.

## 두 출력 형식, 두 파이프라인

| 항목 | HWPX (결과보고서) | PPTX (제안서 양식 기반) |
|------|----------------|---------------------|
| 대상 문서 | 공공기관 결과보고서 (수십 페이지 본문) | 제안서·발표자료 (10~30장 슬라이드) |
| 핵심 엔진 | **비전 기반 스타일 추출** (Ollama/Gemini) | **결정론적 템플릿 주입** (md2pptx-template) |
| LLM 역할 | 양식 이미지 → StyleJSON, 여러 MD → 통합 본문 합성 | **없음** (LLM 호출 0회) |
| 외부 API 필요 | 선택 (Ollama 로컬 또는 Gemini) | **없음** |
| 원본 디자인 보존 | 스타일 참조 (폰트·여백·헤딩) | byte-level 완벽 보존 (XML 그대로) |
| 입력 | 계획서 HWP + Work Plan PDF + Wrap Up PDF → 통합 MD | 단일 MD + 양식 PPTX |
| 출력 | 새 HWPX 파일 | 양식을 수정한 PPTX |
| 상세 문서 | [hwpx-vision-mcp.md](hwpx-vision-mcp.md) | [pptx-md2pptx.md](pptx-md2pptx.md) |

## UI 구성 (localhost:5173)

- 상단 탭 **📝 HWPX / 🎨 PPTX** 로 두 파이프라인 전환
- 공통: 좌측 파일 탐색기, 중앙 MD 프리뷰, 우측 로그·결과 패널
- HWPX 탭: 📝 MD 합성 (여러 MD → 통합 MD, LLM 사용) + 🎯 HWPX 생성 (주입 문서 + 양식 문서 조합)
- PPTX 탭: 단일 카드 "MD + 양식 PPTX → 결과 PPTX" (원클릭, 몇 초)

## 공통 흐름

루트 [README.md](../README.md) 의 "공통 흐름" 섹션 참조.

## 디렉토리

```
.
├── backend/              FastAPI (포트 8765)
│   ├── routes/           hwpx / pptx / files / ollama / report
│   └── services/         composer / llm / renderer / mcp_bridge
├── frontend/             Vite + React (포트 5173)
├── doc_mcp/
│   ├── hwpx_vision/      HWPX 파이프라인 (비전 기반, MCP 서버 포함)
│   └── md2pptx/          PPTX 파이프라인 (결정론적, unpack→edit-XML→pack)
├── docs/                 이 문서들
└── _context/             사용자 자료 (gitignored)
```

## 실행

```bash
install.bat   # 최초 1회 — Python venv, npm install
start.bat     # 백엔드+프론트 동시 기동 + 브라우저 오픈
```
