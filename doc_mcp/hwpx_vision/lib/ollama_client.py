from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Iterable, Optional

import httpx


OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# 비전은 기본 빈 값 — Settings 에서 선택 시에만 활성화 (HWPX 비전은 클라우드 Gemini 권장)
DEFAULT_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "")
DEFAULT_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "qwen2.5:3b")


def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def generate_vision(
    image_paths: Iterable[str],
    prompt: str,
    system: Optional[str] = None,
    model: str = DEFAULT_VISION_MODEL,
    format_json: bool = True,
    timeout: float = 300.0,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [_b64(p) for p in image_paths],
        "stream": False,
    }
    if system:
        payload["system"] = system
    if format_json:
        payload["format"] = "json"

    with httpx.Client(timeout=timeout) as client:
        r = client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        r.raise_for_status()
        return r.json().get("response", "")


def generate_text(
    prompt: str,
    system: Optional[str] = None,
    model: str = DEFAULT_TEXT_MODEL,
    timeout: float = 600.0,
) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    with httpx.Client(timeout=timeout) as client:
        r = client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        r.raise_for_status()
        return r.json().get("response", "")


def health() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []
