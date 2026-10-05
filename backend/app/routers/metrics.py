"""/api/metrics（A5）：任务成功率、平均耗时、回退次数、SSE 订阅数、存储占用。

个人规模下从现有表即时聚合，不引入独立指标存储。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from .. import config
from ..database import SessionLocal
from ..models import Chapter, DownloadTask, MediaItem, Note, Novel
from ..services import storage as storage_svc
from ..services.task_manager import bus

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

_FALLBACK_MARK = "自动切换"  # task_manager 回退链切换时写入 message/log 的标记


@router.get("")
async def metrics() -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    async with SessionLocal() as db:
        # --- 任务统计（近 30 天） ---
        by_status_rows = (await db.execute(
            select(DownloadTask.status, func.count(DownloadTask.id))
            .where(func.substr(DownloadTask.created_at, 1, 10) >= since)
            .group_by(DownloadTask.status)
        )).all()
        by_status = {s: c for s, c in by_status_rows}
        completed = by_status.get("completed", 0)
        failed = by_status.get("failed", 0)
        terminal = completed + failed
        # 平均耗时（完成且记录了起止时间的任务）
        durations = (await db.execute(
            select(
                func.avg(
                    func.julianday(DownloadTask.finished_at) - func.julianday(DownloadTask.started_at)
                )
            ).where(
                DownloadTask.status == "completed",
                DownloadTask.started_at.is_not(None),
                DownloadTask.finished_at.is_not(None),
                func.substr(DownloadTask.created_at, 1, 10) >= since,
            )
        )).scalar()
        avg_duration_sec = round(float(durations) * 86400, 1) if durations else None
        # 回退次数：失败后自动切换工具的任务数
        fallback_count = (await db.execute(
            select(func.count(DownloadTask.id)).where(
                DownloadTask.message.contains(_FALLBACK_MARK),
                func.substr(DownloadTask.created_at, 1, 10) >= since,
            )
        )).scalar() or 0
        # 失败原因分布（A2 错误码）
        error_rows = (await db.execute(
            select(DownloadTask.error_code, func.count(DownloadTask.id))
            .where(DownloadTask.status == "failed",
                   func.substr(DownloadTask.created_at, 1, 10) >= since)
            .group_by(DownloadTask.error_code)
        )).all()
        by_error_code = {c or "UNKNOWN": n for c, n in error_rows}

        # --- 库存规模 ---
        counts = {
            "novels": (await db.execute(select(func.count(Novel.id)))).scalar() or 0,
            "chapters": (await db.execute(select(func.count(Chapter.id)))).scalar() or 0,
            "notes": (await db.execute(select(func.count(Note.id)))).scalar() or 0,
            "media": (await db.execute(select(func.count(MediaItem.id)))).scalar() or 0,
        }

    return {
        "window_days": 30,
        "tasks": {
            "by_status": by_status,
            "total": sum(by_status.values()),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / terminal, 4) if terminal else None,
            "avg_duration_sec": avg_duration_sec,
            "fallback_count": fallback_count,
            "by_error_code": by_error_code,
        },
        "sse": bus.stats(),
        "library": counts,
        "storage": await _storage(),
    }


async def _storage() -> dict:
    """存储占用（沿用 storage 服务；同步磁盘遍历放线程，失败不拖垮指标端点）。"""
    try:
        import asyncio

        from ..models import Setting

        async with SessionLocal() as db:
            row = await db.get(Setting, "storage_quota_gb")
        quota = float(row.value) if row is not None and isinstance(row.value, (int, float)) \
            else config.DEFAULT_STORAGE_QUOTA_GB
        return await asyncio.to_thread(storage_svc.storage_stats, quota)
    except Exception:
        return {}
