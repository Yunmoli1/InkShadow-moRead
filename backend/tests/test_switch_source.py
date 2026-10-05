"""一键换源回归：强制重建 / 同章数换来源 / 接口校验。"""
import tempfile
import uuid
from pathlib import Path

import pytest


def _make_novel_txt(n_chapters=5):
    parts = []
    for i in range(1, n_chapters + 1):
        parts.append(f"第{i}章 测试章节")
        parts.append("这是测试正文内容，用于验证章节解析流程是否正常工作。" * 8)
    header = "测试之书\n\n"
    return (header + "\n\n".join(parts)).encode("utf-8")


def _make_lncrawl_dir(n_chapters: int, root: Path, title="换源测试书") -> Path:
    d = root / f"lncrawl-{uuid.uuid4().hex[:8]}"
    (d / "artifacts" / "book").mkdir(parents=True, exist_ok=True)
    (d / "artifacts" / "book" / "meta.txt").write_text(
        "https://mirror-b.example.com/book\n\n----------------------------------------\n\n"
        f"{title}\nby, 测试者\n\n----------------------------------------\n\n简介\n\n"
        f"----------------------------------------\n\nChapters: {n_chapters}\n",
        encoding="utf-8",
    )
    for i in range(1, n_chapters + 1):
        (d / "artifacts" / "book" / f"{i:05d}.txt").write_text(
            f"第{i}章 换源章节\n\n来自镜像B的第{i}章内容。" * 5, encoding="utf-8"
        )
    return d / "artifacts" / "book"


def test_switch_source_rebuild_and_url_update(client, monkeypatch):
    """回归：换源强制重建章节并更新 source_url（章节数变化场景）。"""
    import asyncio

    from app.database import SessionLocal
    from app.models import Novel
    from app.services.novel_parser import import_lncrawl_output

    # 源 A：5 章书
    r = client.post("/api/novels/import", files=[
        ("files", (f"sw_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(5), "text/plain")),
    ])
    assert r.status_code == 200
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
    nid = novel["id"]

    async def _set_source(url):
        async with SessionLocal() as db:
            n = await db.get(Novel, nid)
            n.source_url = url
            await db.commit()
    asyncio.run(_set_source("https://mirror-a.example.com/book"))

    # 换到源 B：lncrawl 产物 7 章 → 强制重建 + 更新来源
    out = _make_lncrawl_dir(7, Path(tempfile.mkdtemp(prefix="switch-")))
    result = asyncio.run(import_lncrawl_output(
        out, source_url="https://mirror-b.example.com/book", switch_novel_id=nid,
    ))
    assert result.id == nid, "换源应复用同一本书"
    assert result.source_url == "https://mirror-b.example.com/book"
    assert result.total_chapters == 7

    chapters = client.get(f"/api/novels/{nid}/chapters", params={"limit": 50}).json()
    assert chapters["total"] == 7
    content = client.get(f"/api/novels/{nid}/chapters/{chapters['items'][0]['id']}/content").json()
    assert "镜像B" in content["content"]
    client.delete(f"/api/novels/{nid}")


def test_switch_source_same_count_updates_url(client):
    """回归：章节数相同的换源也更新来源 URL（幂等分支）。"""
    import asyncio

    from app.database import SessionLocal
    from app.models import Novel
    from app.services.novel_parser import import_lncrawl_output

    r = client.post("/api/novels/import", files=[
        ("files", (f"sw2_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200
    nid = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]["id"]

    async def _set_source(url):
        async with SessionLocal() as db:
            n = await db.get(Novel, nid)
            n.source_url = url
            n.subscribed = True
            await db.commit()
    asyncio.run(_set_source("https://mirror-a.example.com/book"))

    out = _make_lncrawl_dir(3, Path(tempfile.mkdtemp(prefix="switch2-")))
    result = asyncio.run(import_lncrawl_output(
        out, source_url="https://mirror-c.example.com/book", switch_novel_id=nid,
    ))
    assert result.source_url == "https://mirror-c.example.com/book"
    assert result.total_chapters == 3
    assert result.new_chapters == 0, "换源不应累计新章数"
    client.delete(f"/api/novels/{nid}")


def test_switch_source_endpoint_validation(client, monkeypatch):
    """回归：switch-source 接口校验（404 / 同源 400 / 正常创建任务）。"""
    created = {}

    class FakeTask:
        id = "fake-task-id"
        status = "queued"

    async def fake_create_task(**kwargs):
        created.update(kwargs)
        return FakeTask()

    from app.services import task_manager

    monkeypatch.setattr(task_manager.manager, "create_task", fake_create_task)

    r = client.post("/api/novels/no-such-novel/switch-source",
                    json={"new_url": "https://mirror-x.example.com/book"})
    assert r.status_code == 404

    r0 = client.post("/api/novels/import", files=[
        ("files", (f"sw3_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r0.status_code == 200
    nid = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]["id"]

    async def _set_source(url):
        import asyncio as _aio

        from app.database import SessionLocal
        from app.models import Novel

        async def _go():
            async with SessionLocal() as db:
                n = await db.get(Novel, nid)
                n.source_url = url
                await db.commit()
        await _go()
    asyncio_run(_set_source("https://mirror-a.example.com/book"))

    same = client.post(f"/api/novels/{nid}/switch-source",
                       json={"new_url": "https://mirror-a.example.com/book"})
    assert same.status_code == 400 and "相同" in same.json()["detail"]

    ok = client.post(f"/api/novels/{nid}/switch-source",
                     json={"new_url": "https://mirror-b.example.com/book"})
    assert ok.status_code == 200 and ok.json()["task_id"] == "fake-task-id"
    assert created["options"]["switch_novel_id"] == nid
    client.delete(f"/api/novels/{nid}")


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
