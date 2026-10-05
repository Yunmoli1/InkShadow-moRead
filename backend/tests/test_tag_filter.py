"""B1 标签筛选：tag 参数过滤列表 + tag-list 聚合。"""
from app.database import SessionLocal
from app.models import MediaItem, Novel


def _seed():
    import asyncio

    async def go():
        async with SessionLocal() as db:
            db.add(Novel(title="修仙传一", tags=["仙侠", "玄幻"]))
            db.add(Novel(title="都市日常", tags=["都市"]))
            db.add(MediaItem(media_type="image", title="山景", tags=["风景"]))
            await db.commit()
    asyncio.run(go())


def test_novel_tag_filter_and_list(client):
    _seed()
    # 按标签过滤
    r = client.get("/api/novels", params={"tag": "仙侠"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["title"] == "修仙传一"
    total = r.json()["total"]
    assert total == 1
    # tag-list 聚合
    tags = {t["tag"]: t["count"] for t in client.get("/api/novels/tag-list").json()}
    assert tags["仙侠"] == 1 and tags["都市"] == 1


def test_media_tag_filter_and_list(client):
    r = client.get("/api/media", params={"tag": "风景"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    tags = {t["tag"]: t["count"] for t in client.get("/api/media/tag-list").json()}
    assert tags.get("风景", 0) >= 1
