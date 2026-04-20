# hwpx_vision MCP

비전 모델(기본 `gemma3n:e4b`)이 참조 HWP 페이지 이미지에서 스타일 구조를 추출하고, Markdown에 적용해 HWPX로 저장하는 MCP 서버.

## Tools

| 이름 | 입력 | 출력 |
|------|------|------|
| `analyze_style_from_image` | `image_paths: list[str]`, `use_cache: bool`, `model?: str` | `StyleJSON` dict |
| `apply_style_to_md` | `md_path: str`, `output_hwpx: str`, `style_json?: dict` | `{path, bytes}` |
| `render_hwp_to_images` | `source_path: str`, `dpi: int`, `out_dir?: str` | `list[str]` PNG 경로 |

## 실행

```bash
python -m mcp.hwpx_vision.server
```

## 환경변수

- `OLLAMA_BASE_URL` (기본 `http://localhost:11434`)
- `OLLAMA_VISION_MODEL` (기본 `gemma3n:e4b`)
- `OLLAMA_TEXT_MODEL` (기본 `gemma3n:e4b`)
- `HWPX_VISION_CACHE` (기본 `.style_cache`)

## 의존성

- `python-hwpx` (MD→HWPX)
- `PyMuPDF` (PDF→PNG)
- `LibreOffice` 외부 설치 (HWP/HWPX→PDF, PATH에 `soffice` 필요)
- Ollama 로컬 서버 + `gemma3n:e4b` 모델
