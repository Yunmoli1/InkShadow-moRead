"""FTS5 章节正文全文索引（B4）。

- 虚表 chapters_fts（trigram tokenizer，支持中文子串匹配；旧 SQLite 自动降级）。
- 惰性维护：fts_state 记录每本书已索引的章节数与时间；搜索前比对
  章节 real count 与 novel.updated_at，过期则整本重建索引（含磁盘文件章节）。
- 查询走 MATCH + snippet()，万章级书 <100ms；<3 字符的查询（trigram 下限）
  或 FTS 不可用时由调用方回退到 LIKE 扫描，接口格式不变。
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

from .. import config
from ..config import DB_PATH

log = logging.getLogger("moread.fts")

FTS_TABLE = "chapters_fts"
STATE_TABLE = "fts_state"
_MIN_TRIGRAM_LEN = 3


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def try_setup_fts() -> bool:
    """创建 FTS 虚表（幂等）。返回 FTS 是否可用。启动时调用一次。"""
    try:
        conn = _connect()
    except Exception as exc:
        log.warning("FTS setup skipped (db unavailable): %s", exc)
        return False
    try:
        have = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name=?", (FTS_TABLE,)
        ).fetchone()[0]
        if not have:
            conn.execute(
                f"CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5("
                "chapter_id UNINDEXED, title, content, tokenize='trigram')")
            log.info("FTS5 virtual table created (trigram)", extra={"event": "fts-setup"})
        else:
            return True  # 已存在（此前初始化成功）
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {STATE_TABLE} ("
            "novel_id TEXT PRIMARY KEY, chapter_count INTEGER, indexed_at TEXT)")
        return True
    except Exception as exc:
        # 老版本 SQLite 无 trigram/FTS5：功能降级，搜索走 LIKE
        log.warning("FTS5 unavailable, search falls back to LIKE: %s", exc)
        try:
            conn.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
        except Exception:
            pass
        return False
    finally:
        conn.close()


_fts_available: bool | None = None


def fts_available() -> bool:
    global _fts_available
    if _fts_available is None:
        _fts_available = try_setup_fts()
    return _fts_available


def _index_novel_sync(novel_id: str) -> int:
    """（重）建一本书的索引：读章节（含磁盘文件）→ 整体替换 FTS 条目。"""
    from sqlalchemy import select

    from ..database import SessionLocal
    from ..models import Chapter, Novel

    # 同步上下文里拿不到 AsyncSession：直接用原生 SQL 读章节
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, idx, title, content, content_path FROM chapters "
            "WHERE novel_id = ? ORDER BY idx", (novel_id,)).fetchall()
        entries = []
        for cid, _idx, title, content, content_path in rows:
            if not content and content_path:
                p = config.DATA_DIR / content_path
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        content = ""
            if not content:
                continue
            entries.append((cid, title or "", content))
        conn.execute("BEGIN")
        conn.execute(
            f"DELETE FROM {FTS_TABLE} WHERE chapter_id IN "
            f"(SELECT id FROM chapters WHERE novel_id = ?)", (novel_id,))
        conn.executemany(
            f"INSERT INTO {FTS_TABLE} (chapter_id, title, content) VALUES (?, ?, ?)",
            entries)
        conn.execute(
            f"INSERT INTO {STATE_TABLE} (novel_id, chapter_count, indexed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(novel_id) DO UPDATE SET chapter_count=excluded.chapter_count, "
            "indexed_at=excluded.indexed_at",
            (novel_id, len(rows), datetime.now(timezone.utc).isoformat()))
        conn.execute("COMMIT")
        return len(entries)
    finally:
        conn.close()


async def ensure_indexed(novel_id: str, real_count: int, updated_at: datetime | None) -> None:
    """索引过期（章节数变化或小说更新过）时在后台线程重建。"""
    from sqlalchemy import text

    from ..database import SessionLocal

    async with SessionLocal() as db:
        row = (await db.execute(
            text(f"SELECT chapter_count, indexed_at FROM {STATE_TABLE} WHERE novel_id=:n"),
            {"n": novel_id},
        )).first()
    stale = row is None or row[0] != real_count
    if not stale and updated_at is not None and row is not None:
        try:
            stale = datetime.fromisoformat(row[1]) < updated_at
        except ValueError:
            stale = True
    if not stale:
        return
    indexed = await asyncio.to_thread(_index_novel_sync, novel_id)
    log.info("fts indexed novel %s: %d chapters", novel_id, indexed,
             extra={"event": "fts-index", "tool": "fts", "code": novel_id[:8]})


def match_query(q: str) -> str | None:
    """把用户查询转成 FTS MATCH 语法（每词组引号防注入/语法错）。

    任一词 <3 字符时返回 None（trigram 下限，调用方回退 LIKE）。
    """
    terms = [t for t in q.strip().split() if t] or [q.strip()]
    if any(len(t) < _MIN_TRIGRAM_LEN for t in terms):
        return None
    return " ".join(f'"{t.replace(chr(34), "")}"' for t in terms)


async def fts_search(novel_id: str, match: str, raw_query: str, limit: int = 50) -> list[dict]:
    """FTS 查询单本书：返回 {chapter_id, chapter_idx, title, hits:[{where,snippet}]}。"""
    from sqlalchemy import text

    from ..database import SessionLocal

    sql = text(
        f"SELECT c.id, c.idx, c.title, "
        f"snippet({FTS_TABLE}, 2, '', '', '…', 18) AS snip "
        f"FROM {FTS_TABLE} JOIN chapters c ON c.id = {FTS_TABLE}.chapter_id "
        f"WHERE {FTS_TABLE} MATCH :m AND c.novel_id = :n "
        f"ORDER BY rank LIMIT :lim")
    async with SessionLocal() as db:
        rows = (await db.execute(sql, {"m": match, "n": novel_id, "lim": limit})).all()
    ql = raw_query.strip().lower()
    results: list[dict] = []
    for cid, idx, title, snip in rows:
        hits = []
        if ql and ql in (title or "").lower():
            hits.append({"where": "title", "snippet": title[:80]})
        if snip:
            hits.append({"where": "content", "snippet": snip.replace("\n", " ")})
        if hits:
            results.append({"chapter_id": cid, "chapter_idx": idx, "title": title, "hits": hits})
    return results
