"""MoRead backend entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import init_db
from .routers import media, novels, settings, tasks, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    await init_db()
    yield


app = FastAPI(
    title="墨读 MoRead API",
    description="个人本地知识库：通过调度专业开源工具实现小说/图片/音频/视频/网页的获取、管理与预览。",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-only app; frontend may run on any local port
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router)
app.include_router(tasks.router)
app.include_router(novels.router)
app.include_router(media.router)
app.include_router(settings.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "app": "MoRead", "version": "1.0.0"}


# --- serve frontend build (single-binary deployment) -----------------------
STATIC_DIR = config.STATIC_FRONTEND_DIR
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8686, reload=False)
