from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import files, hwpx, ollama, report


app = FastAPI(title="hwpx-writer-backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(ollama.router)
app.include_router(report.router)
app.include_router(hwpx.router)


@app.get("/api/ping")
def ping() -> dict:
    return {"ok": True}
