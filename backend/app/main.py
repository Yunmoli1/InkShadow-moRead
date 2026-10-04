"""MoRead backend entrypoint."""
from __future__ import annotations

import asyncio
import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
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
    # 任务接管：排队中的重新入队，运行中的标记中断（可重试）
    from .services.task_manager import manager

    requeued = await manager.takeover_on_startup()
    if requeued:
        print(f"[MoRead] 服务重启后已重新入队 {requeued} 个排队任务")
    # 追更订阅后台循环
    from .services.updater import auto_loop

    updater_task = asyncio.create_task(auto_loop())
    yield
    updater_task.cancel()


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


# --- 可选访问令牌（局域网访问保护） ----------------------------------------
# 设置中配置 access_token 后，/api/*（除 health）需要请求头 X-MoRead-Token
# 或查询参数 ?token= 匹配；未设置则完全开放（纯本机使用不受影响）。
from .services.token_guard import current_token as _current_token


@app.middleware("http")
async def access_token_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path != "/api/health":
        token = await _current_token()
        if token:
            provided = (
                request.headers.get("x-moread-token")
                or request.query_params.get("token")
                or ""
            )
            if not hmac.compare_digest(provided, token):
                return JSONResponse({"detail": "需要访问令牌"}, status_code=401)
    return await call_next(request)


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
