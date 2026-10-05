"""SQLite 例行维护（A4）：空闲时段 wal_checkpoint(TRUNCATE) + VACUUM。

长运行服务下 WAL 文件会持续增长（checkpoint 因长读事务/繁忙而推迟），
每日一次 TRUNCATE checkpoint + VACUUM 保证 WAL 回收、页整理与查询计划更新。
维护用独立的原生 sqlite3 连接执行（VACUUM 不能在事务内运行），
与业务连接（WAL 模式、busy_timeout 5s）互不阻塞。
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger("moread.maintenance")

# 首次延迟 10 分钟（避开启动高峰），之后每 24h 一次
INITIAL_DELAY_SEC = 10 * 60
INTERVAL_SEC = 24 * 3600


def run_maintenance(db_path: Path) -> dict:
    """执行一次 checkpoint(TRUNCATE) + VACUUM，返回维护报告。"""
    report: dict = {"checkpoint": None, "vacuum_ok": False, "wal_pages_after": None}
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    try:
        # 返回 (busy, log, checkpointed)；busy=1 表示仍有活跃读事务阻止完全截断
        row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        report["checkpoint"] = {"busy": row[0], "log_pages": row[1], "checkpointed": row[2]}
        # WAL 模式下 VACUUM 会重建数据库文件，需在事务外执行（isolation_level=None）
        conn.execute("VACUUM")
        report["vacuum_ok"] = True
        report["wal_pages_after"] = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()[1]
    finally:
        conn.close()
    log.info("sqlite maintenance done: %s", report, extra={"event": "db-maintenance"})
    return report


async def maintenance_loop(db_path: Path | None = None) -> None:
    """后台例行维护循环；异常不中断服务，下个周期重试。"""
    from .. import config

    path = db_path or config.DB_PATH
    await asyncio.sleep(INITIAL_DELAY_SEC)
    while True:
        try:
            if path.exists():
                await asyncio.to_thread(run_maintenance, path)
        except Exception as exc:
            log.warning("sqlite maintenance failed (will retry next cycle): %s", exc)
        await asyncio.sleep(INTERVAL_SEC)


def warn_if_network_path(db_path: Path) -> None:
    """数据库置于网络盘（UNC 路径）在断网/延迟下极易损坏——启动时大声告警。"""
    p = str(db_path)
    if p.startswith("\\\\") or p.startswith("//"):
        log.warning(
            "数据库位于网络路径 %s：SQLite 在网络盘上可能损坏，强烈建议迁移到本地磁盘"
            "（设置 MOREAD_DATA_DIR 指向本地目录）", db_path, extra={"event": "network-db-warning"},
        )
