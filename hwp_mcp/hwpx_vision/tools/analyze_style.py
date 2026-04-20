from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..lib.ollama_client import generate_vision
from ..lib.style_schema import StyleJSON, default_preset
from ..lib.vision_prompt import VISION_SYSTEM, VISION_USER


CACHE_DIR = Path(os.environ.get("HWPX_VISION_CACHE", ".style_cache"))


def _hash_images(image_paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(image_paths):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def _cache_path(digest: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{digest}.json"


def _parse_with_retry(raw: str, retries: int = 3) -> dict[str, Any]:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("no JSON object in response")
            return json.loads(raw[start : end + 1])
        except Exception as e:
            last_err = e
    raise RuntimeError(f"failed to parse vision JSON: {last_err}")


def analyze_style_from_image(
    image_paths: list[str], use_cache: bool = True, model: str | None = None
) -> dict[str, Any]:
    """
    참조 페이지 이미지를 비전 모델로 분석해 StyleJSON 반환.
    실패 시 기본 프리셋으로 폴백한다.
    """
    if not image_paths:
        preset = default_preset()
        return preset.model_dump()

    digest = _hash_images(image_paths)
    cache_file = _cache_path(digest)
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    try:
        kwargs: dict[str, Any] = {}
        if model:
            kwargs["model"] = model
        raw = generate_vision(
            image_paths=image_paths,
            prompt=VISION_USER,
            system=VISION_SYSTEM,
            format_json=True,
            **kwargs,
        )
        parsed = _parse_with_retry(raw)
        parsed["source_image_hashes"] = [digest]
        style = StyleJSON.model_validate(parsed)
    except (ValidationError, RuntimeError, Exception):
        style = default_preset()
        style.source_image_hashes = [digest]

    result = style.model_dump()
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
