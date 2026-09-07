# ---- 前端构建 ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml* frontend/pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY frontend/ ./
RUN pnpm run build

# ---- 后端运行 ----
FROM python:3.12-slim
WORKDIR /app

# 系统依赖 + 常用下载工具（yt-dlp/gallery-dl/lncrawl 开箱即用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir yt-dlp gallery-dl you-get

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir lightnovel-crawler

COPY backend/ backend/
COPY --from=frontend-build /app/frontend/dist/ frontend/dist/

ENV MOREAD_DATA_DIR=/app/backend/data
EXPOSE 8686

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8686"]
