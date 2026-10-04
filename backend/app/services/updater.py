"""小说追更订阅：定时用 lncrawl --resume 增量下载新章节。

- check_novel：为一本订阅书创建增量下载任务（走任务中心，用户可见进度）。
- auto_loop：每 6 小时自动检查所有订阅书（每本书 6 小时内不重复检查）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Novel
from . import tool_registry
from .task_manager import manager

CHECK_INTERVAL_HOURS = 6
_MIN_BYTES_PER_CHAPTER = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def check_novel(novel_id: str) -> dict:
    """为一本订阅书发起增量检查（lncrawl --resume 只下载缺失章节）。"""
    async with SessionLocal() as db:
        n = await db.get(Novel, novel_id)
        if n is None:
            raise ValueError("小说不存在")
        if not n.subscribed:
            raise ValueError("该书未开启追更订阅")
        if not n.source_url:
            raise ValueError("该书没有来源 URL，无法检查更新（仅支持通过工具抓取的书）")
        url, tool, book_title = n.source_url, "lncrawl", n.title
        n.last_check_at = _now()
        n.last_check_chapters = n.total_chapters or 0
        await db.commit()
    spec = tool_registry.get_spec(tool)
    if spec is None or not tool_registry.resolve_executable(spec):
        raise ValueError("lncrawl 未安装，无法检查更新")
    task = await manager.create_task(
        tool=tool, url=url, options={"format": "txt"}, dest_type="novel",
        title=f"追更检查：{book_title}",
    )
    return {"task_id": task.id, "message": "已开始检查更新（增量下载，完成后书架显示新章数）"}


async def auto_loop() -> None:
    """后台循环：周期性检查所有订阅书。异常不中断循环。"""
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_HOURS * 3600)
            await check_all(reason="auto")
        except asyncio.CancelledError:
            return
        except Exception:
            continue


async def check_all(reason: str = "manual") -> dict:
    """检查所有订阅书（跳过 6 小时内已检查的）。"""
    cutoff = _now().timestamp() - CHECK_INTERVAL_HOURS * 3600
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Novel).where(Novel.subscribed.is_(True))
        )).scalars().all()
        targets = []
        for n in rows:
            if n.last_check_at is None or n.last_check_at.timestamp() < cutoff:
                targets.append(n.id)
    results = {"checked": 0, "skipped": 0, "errors": []}
    for nid in targets:
        try:
            await check_novel(nid)
            results["checked"] += 1
        except ValueError as exc:
            results["skipped"] += 1
            results["errors"].append(str(exc))
        except Exception:
            results["skipped"] += 1
        await asyncio.sleep(2)  # 间隔启动，避免并发风暴
    return results
