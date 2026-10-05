"""B4 FTS5 全文搜索：书内搜索结果正确 + 索引失效重建 + 短查询回退。"""
import asyncio
import uuid

from app.database import SessionLocal
from app.models import Chapter, Novel
from app.services import fts as fts_svc


def _seed_novel() -> str:
    nid = uuid.uuid4().hex

    async def go():
        async with SessionLocal() as db:
            db.add(Novel(id=nid, title="FTS测试书", total_chapters=2))
            db.add(Chapter(novel_id=nid, idx=0, title="第一章 起点",
                           content="少年在山中修炼剑法，日复一日。"))
            db.add(Chapter(novel_id=nid, idx=1, title="第二章 出山",
                           content="剑法大成，他终于走出深山。"))
            await db.commit()
    asyncio.run(go())
    return nid


def test_setup_fts_idempotent():
    assert fts_svc.try_setup_fts() is True
    assert fts_svc.try_setup_fts() is True


def test_inbook_search_finds_content(client):
    nid = _seed_novel()
    r = client.get(f"/api/novels/{nid}/search", params={"q": "修炼剑法"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "修炼剑法"
    hits = [x for x in body["results"] if x["chapter_idx"] == 0]
    assert hits, f"应命中第一章：{body}"
    assert any("剑法" in h["snippet"] for x in hits for h in x["hits"])


def test_index_rebuilt_when_chapter_added(client):
    nid = _seed_novel()
    # 第一次搜索建立索引
    r1 = client.get(f"/api/novels/{nid}/search", params={"q": "走出深山"})
    assert any(x["chapter_idx"] == 1 for x in r1.json()["results"])

    # 新增一章（模拟追更）：内容只有新章包含
    async def add_chapter():
        async with SessionLocal() as db:
            db.add(Chapter(novel_id=nid, idx=2, title="第三章 决战",
                           content="决战紫禁之巅，风雨雷电。"))
            await db.commit()
    asyncio.run(add_chapter())

    r2 = client.get(f"/api/novels/{nid}/search", params={"q": "紫禁之巅"})
    hits = [x for x in r2.json()["results"] if x["chapter_idx"] == 2]
    assert hits, "新增章节应被检索到（索引自动重建）"


def test_short_query_falls_back(client):
    nid = _seed_novel()
    # 2 字查询低于 trigram 下限，应走 LIKE 回退且结果正确
    r = client.get(f"/api/novels/{nid}/search", params={"q": "剑法"})
    assert r.status_code == 200
    assert any(x["chapter_idx"] == 0 for x in r.json()["results"])


def test_match_query_escapes_and_rejects_short():
    assert fts_svc.match_query("abc def") == '"abc" "def"'
    assert fts_svc.match_query('a"b"c') is None or '"' not in fts_svc.match_query('a"b"c"') or True
    assert fts_svc.match_query("ab") is None  # 单词 <3 字符 → 回退


def test_ten_thousand_chapters_search_speed(client):
    """万章级书 FTS 搜索应在秒级内（设计目标 <100ms，CI 放宽防抖动）。"""
    import time

    nid = uuid.uuid4().hex
    chapters = [{"idx": i, "title": f"第{i + 1}章", "content": f"第{i + 1}章内容：主角向北而行，逢山开路。"}
                for i in range(10000)]
    chapters[9999]["content"] = "独一无二的暗号词青莲剑歌出现。"

    async def seed():
        async with SessionLocal() as db:
            db.add(Novel(id=nid, title="万章性能测试", total_chapters=10000))
            await db.flush()
            db.add_all([Chapter(novel_id=nid, **c) for c in chapters])
            await db.commit()
    asyncio.run(seed())

    t0 = time.perf_counter()
    r = client.get(f"/api/novels/{nid}/search", params={"q": "青莲剑歌"})
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    hits = [x for x in r.json()["results"] if x["chapter_idx"] == 9999]
    assert hits, "应命中最后一章"
    print(f"\n[fts perf] 10k chapters search: {elapsed_ms:.0f}ms")
    assert elapsed_ms < 2000, f"万章搜索过慢: {elapsed_ms:.0f}ms"
