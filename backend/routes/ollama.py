from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from doc_mcp.hwpx_vision.lib.ollama_client import health, list_models

from backend.services.llm import load_config, save_config


router = APIRouter(prefix="/api", tags=["provider"])


@router.get("/ollama/health")
def ollama_health() -> dict[str, Any]:
    ok = health()
    models = list_models() if ok else []
    return {
        "ok": ok,
        "models": models,
        "has_gemma_e4b": any("gemma3n:e4b" in m or "gemma4:e4b" in m for m in models),
        "has_gemma_e2b": any("gemma3n:e2b" in m or "gemma4:e2b" in m for m in models),
    }


class ConfigBody(BaseModel):
    provider: str = "ollama"
    gemini_api_key: str = ""
    model_text: str = "gemma3n:e4b"
    model_vision: str = "gemma3n:e4b"
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"


@router.get("/config")
def get_config() -> dict[str, Any]:
    cfg = load_config()
    masked = dict(cfg)
    if masked.get("gemini_api_key"):
        masked["gemini_api_key"] = "***" + masked["gemini_api_key"][-4:]
    return masked


@router.post("/config")
def set_config(body: ConfigBody) -> dict[str, Any]:
    new_cfg = body.model_dump()
    # 마스크된 값(***XXXX) 이나 빈 값으로 저장된 키를 덮어쓰지 않는다
    existing = load_config()
    incoming_key = new_cfg.get("gemini_api_key", "")
    if not incoming_key or incoming_key.startswith("***"):
        new_cfg["gemini_api_key"] = existing.get("gemini_api_key", "")
    save_config(new_cfg)
    return {"ok": True}


class GeminiTestBody(BaseModel):
    api_key: str
    model: str = "gemini-2.5-flash"


@router.post("/gemini/test")
def gemini_test(body: GeminiTestBody) -> dict[str, Any]:
    if not body.api_key or body.api_key.startswith("***"):
        return {"ok": False, "error": "API 키가 입력되지 않았습니다."}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{body.model}:generateContent?key={body.api_key}"
    payload = {"contents": [{"parts": [{"text": "ping"}]}], "generationConfig": {"maxOutputTokens": 10}}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            preview = ""
            for cand in data.get("candidates", []):
                for p in cand.get("content", {}).get("parts", []):
                    if "text" in p:
                        preview = p["text"]
                        break
            return {"ok": True, "model": body.model, "preview": preview[:80]}
        return {"ok": False, "status": r.status_code, "error": r.text[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/gemini/models")
def gemini_models(api_key: str = "") -> dict[str, Any]:
    if not api_key or api_key.startswith("***"):
        return {"ok": False, "models": []}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
        if r.status_code == 200:
            data = r.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    models.append({
                        "id": name,
                        "display": m.get("displayName", name),
                        "version": m.get("version", ""),
                    })
            return {"ok": True, "models": models}
        return {"ok": False, "error": r.text[:500], "models": []}
    except Exception as e:
        return {"ok": False, "error": str(e), "models": []}
