"""LLM Provider 추상화: Ollama(로컬) / Gemini(클라우드) 토글."""
from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator, Iterable, Optional

import httpx


CONFIG_PATH = Path(os.environ.get("HWPX_CONFIG", Path.home() / ".config" / "hwpx_writer" / "config.json"))


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"provider": "ollama", "gemini_api_key": "", "model_text": "gemma3n:e4b", "model_vision": "gemma3n:e4b"}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate_text(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]: ...

    @abstractmethod
    async def generate_vision(self, image_paths: Iterable[str], prompt: str, system: Optional[str] = None) -> str: ...


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", text_model: str = "gemma3n:e4b", vision_model: str = "gemma3n:e4b"):
        self.base_url = base_url
        self.text_model = text_model
        self.vision_model = vision_model

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        payload = {"model": self.text_model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as r:
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    piece = chunk.get("response", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break

    async def generate_vision(self, image_paths: Iterable[str], prompt: str, system: Optional[str] = None) -> str:
        images_b64 = [base64.b64encode(Path(p).read_bytes()).decode("ascii") for p in image_paths]
        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": images_b64,
            "stream": False,
            "format": "json",
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{self.base_url}/api/generate", json=payload)
            r.raise_for_status()
            return r.json().get("response", "")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, text_model: str = "gemini-2.5-flash", vision_model: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("Gemini API 키가 설정되지 않았습니다.")
        self.api_key = api_key
        self.text_model = text_model
        self.vision_model = vision_model

    def _endpoint(self, model: str) -> str:
        # ?alt=sse 로 SSE 포맷 (data: {...}) 사용 — JSON 배열 파싱 이슈 회피
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

    def _endpoint_sync(self, model: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        parts = [{"text": prompt}]
        body: dict = {"contents": [{"role": "user", "parts": parts}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        yielded_any = False
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", self._endpoint(self.text_model), json=body) as r:
                if r.status_code != 200:
                    err_text = (await r.aread()).decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Gemini {r.status_code}: {err_text[:500]}")
                async for raw in r.aiter_lines():
                    if not raw:
                        continue
                    if not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except Exception:
                        continue
                    for cand in chunk.get("candidates", []):
                        for p in cand.get("content", {}).get("parts", []):
                            t = p.get("text")
                            if t:
                                yielded_any = True
                                yield t
        if not yielded_any:
            # 스트리밍 실패 폴백: 단회 호출로 재시도
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(self._endpoint_sync(self.text_model), json=body)
                r.raise_for_status()
                data = r.json()
                for cand in data.get("candidates", []):
                    for p in cand.get("content", {}).get("parts", []):
                        t = p.get("text")
                        if t:
                            yield t

    async def generate_vision(self, image_paths: Iterable[str], prompt: str, system: Optional[str] = None) -> str:
        parts: list[dict] = [{"text": prompt}]
        for p in image_paths:
            data = base64.b64encode(Path(p).read_bytes()).decode("ascii")
            parts.append({"inline_data": {"mime_type": "image/png", "data": data}})
        body: dict = {"contents": [{"role": "user", "parts": parts}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        body["generationConfig"] = {"responseMimeType": "application/json"}
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(self._endpoint_sync(self.vision_model), json=body)
            r.raise_for_status()
            data = r.json()
            for cand in data.get("candidates", []):
                for p in cand.get("content", {}).get("parts", []):
                    if "text" in p:
                        return p["text"]
            return ""


def get_provider() -> LLMProvider:
    cfg = load_config()
    name = cfg.get("provider", "ollama")
    if name == "gemini":
        return GeminiProvider(
            api_key=cfg.get("gemini_api_key", ""),
            text_model=cfg.get("gemini_text_model", "gemini-2.5-flash"),
            vision_model=cfg.get("gemini_vision_model", "gemini-2.5-flash"),
        )
    return OllamaProvider(
        base_url=cfg.get("ollama_base", "http://localhost:11434"),
        text_model=cfg.get("model_text", "gemma3n:e4b"),
        vision_model=cfg.get("model_vision", "gemma3n:e4b"),
    )
