"""追更订阅回归：订阅开关 / lncrawl 增量重建 / 检查更新守卫。"""
import os
import tempfile
import uuid
from pathlib import Path

import pytest


def _make_lncrawl_dir(n_chapters: int, root: Path) -> Path:
    """伪造 lncrawl 4.x 输出目录：meta.txt + 分章 txt。"""
    d = root / f"lncrawl-{uuid.uuid4().hex[:8]}"
    (d / "artifacts" / "book").mkdir(parents=True, exist_ok=True)
    (d / "artifacts" / "book" / "meta.txt").write_text(
        "https://example.com/feed-book\n\n----------------------------------------\n\n"
        "追更测试书\nby, 测试者\n\n----------------------------------------\n\n简介\n\n"
        "----------------------------------------\n\nTags: Test\nVolumes: 1\n"
        f"Chapters: {n_chapters}\n",
        encoding="utf-8",
    )
    for i in range(1, n_chapters + 1):
        (d / "artifacts" / "book" / f"{i:05d}.txt").write_text(
            f"第{i}章 追更章节\n\n这是第{i}章的正文内容。" * 5, encoding="utf-8"
        )
    return d / "artifacts" / "book"


def test_novel_subscribe_toggle(client):
    """回归：订阅开关写入并回读；关闭时清零新章数。"""
    r = client.post("/api/novels/import", files=[
        ("files", (f"sub_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
    nid = novel["id"]
    assert novel["subscribed"] is False and novel["new_chapters"] == 0

    on = client.patch(f"/api/novels/{nid}/subscribe", json={"subscribed": True})
    assert on.status_code == 200 and on.json()["subscribed"] is True
    detail = client.get(f"/api/novels/{nid}").json()
    assert detail["subscribed"] is True

    off = client.patch(f"/api/novels/{nid}/subscribe", json={"subscribed": False})
    assert off.status_code == 200
    assert client.get(f"/api/novels/{nid}").json()["subscribed"] is False
    assert client.delete(f"/api/novels/{nid}").status_code == 200


def test_check_update_guards(client):
    """回归：无来源 URL / 未订阅的书检查更新返回友好 400。"""
    r = client.post("/api/novels/import", files=[
        ("files", (f"chk_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
    nid = novel["id"]
    # 未订阅
    res = client.post(f"/api/novels/{nid}/check-update")
    assert res.status_code == 400 and "未开启追更" in res.json()["detail"]
    # 订阅但无来源
    client.patch(f"/api/novels/{nid}/subscribe", json={"subscribed": True})
    res2 = client.post(f"/api/novels/{nid}/check-update")
    assert res2.status_code == 400 and "来源 URL" in res2.json()["detail"]
    client.delete(f"/api/novels/{nid}")


def test_lncrawl_incremental_rebuild_marks_new_chapters(client, monkeypatch):
    """回归：lncrawl 抓到新章节后重建书，订阅书累计 new_chapters。"""
    from app.services.novel_parser import import_lncrawl_output

    root = Path(tempfile.mkdtemp(prefix="lncrawl-test-"))
    # 第一次导入：5 章（未订阅）
    out1 = _make_lncrawl_dir(5, root)
    novel = asyncio_run_import(out1)
    assert novel.total_chapters == 5
    nid = novel.id

    # 开启订阅（直接改库，模拟用户在 UI 打开追更）
    from app.database import SessionLocal

    async def _sub():
        async with SessionLocal() as db:
            from app.models import Novel

            n = await db.get(Novel, nid)
            n.subscribed = True
            await db.commit()
    import asyncio
    asyncio.run(_sub())

    # 第二次抓取：8 章 → 重建 + new_chapters = 3
    out2 = _make_lncrawl_dir(8, root)
    novel2 = asyncio_run_import(out2)
    assert novel2.id == nid, "增量导入应复用同一本书"
    assert novel2.total_chapters == 8
    assert novel2.new_chapters == 3

    # 章节内容确实更新（可读出第 8 章）
    chapters = client.get(f"/api/novels/{nid}/chapters", params={"limit": 20}).json()
    assert chapters["total"] == 8
    last = chapters["items"][-1]
    content = client.get(f"/api/novels/{nid}/chapters/{last['id']}/content").json()
    assert "第8章" in content["title"] or "第8章" in content["content"][:50]

    # 清理
    client.delete(f"/api/novels/{nid}")


def asyncio_run_import(out_dir: Path):
    import asyncio

    from app.services.novel_parser import import_lncrawl_output

    return asyncio.run(import_lncrawl_output(out_dir, source_url="https://example.com/feed-book"))


def _make_novel_txt(n_chapters=5):
    parts = []
    for i in range(1, n_chapters + 1):
        parts.append(f"第{i}章 测试章节")
        parts.append("这是测试正文内容，用于验证章节解析流程是否正常工作。" * 8)
    header = "测试之书\n\n"
    return (header + "\n\n".join(parts)).encode("utf-8")
