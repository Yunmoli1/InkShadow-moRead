"""新功能回归：备份 v2 / 书内搜索 / 播放进度 / 访问令牌。"""
import uuid

def _make_novel_txt(n_chapters=5):
    parts = []
    for i in range(1, n_chapters + 1):
        parts.append(f"第{i}章 测试章节")
        parts.append("这是测试正文内容，用于验证章节解析流程是否正常工作。" * 8)
    header = "测试之书\n\n"
    return (header + "\n\n".join(parts)).encode("utf-8")


BIG_BODY = "这是大书备份回归测试的正文内容，需要足够长以触发磁盘存储路径。" * 900


def _make_big_txt() -> bytes:
    parts = []
    for i in range(1, 81):
        parts.append(f"第{i}章 大书章节")
        parts.append(BIG_BODY)
    return ("大书备份测试\n\n" + "\n\n".join(parts)).encode("utf-8")


def test_backup_v2_roundtrip_large_novel(client):
    """回归：>2MB 大书备份后正文不丢失（v2 内联磁盘章节）。"""
    data = _make_big_txt()
    assert len(data) > 2 * 1024 * 1024
    r = client.post("/api/novels/import", files=[
        ("files", (f"big_{uuid.uuid4().hex[:6]}.txt", data, "text/plain")),
    ])
    assert r.status_code == 200 and r.json()["imported"]
    novel = client.get("/api/novels", params={"search": "大书备份测试"}).json()[0]
    nid = novel["id"]

    exp = client.get("/api/backup/export")
    payload = exp.json()
    assert payload["version"] == 2
    book = next(b for b in payload["novels"] if b["title"] == "大书备份测试")
    assert sum(len(c["content"]) for c in book["chapters"]) > 2 * 1024 * 1024, "大书正文应被内联"
    assert client.delete(f"/api/novels/{nid}").status_code == 200
    imp = client.post("/api/backup/import", json=payload)
    assert imp.status_code == 200 and imp.json()["restored_novels"] >= 1
    restored = client.get("/api/novels", params={"search": "大书备份测试"}).json()[0]
    chapters = client.get(f"/api/novels/{restored['id']}/chapters", params={"limit": 200}).json()
    assert chapters["total"] == 80
    sample = client.get(
        f"/api/novels/{restored['id']}/chapters/{chapters['items'][5]['id']}/content"
    ).json()
    assert "大书备份回归测试" in sample["content"]
    assert client.delete(f"/api/novels/{restored['id']}").status_code == 200


def test_novel_in_book_search(client):
    """回归：书内全文搜索命中正文并返回片段。"""
    r = client.post("/api/novels/import", files=[
        ("files", (f"srch_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()[0]
    res = client.get(f"/api/novels/{novel['id']}/search", params={"q": "验证章节解析"})
    body = res.json()
    assert res.status_code == 200 and len(body["results"]) >= 1
    hit = body["results"][0]
    assert hit["hits"] and "验证章节解析" in hit["hits"][-1]["snippet"]
    assert client.delete(f"/api/novels/{novel['id']}").status_code == 200


def test_media_progress_and_backfill(client):
    """回归：播放进度保存 + 补建接口可用。"""
    client.post("/api/media/batch-import", files=[
        ("files", ("pv.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 500, "image/png")),
    ])
    media = client.get("/api/media", params={"media_type": "image"}).json()[0]
    mid = media["id"]
    r = client.patch(f"/api/media/{mid}/progress", json={"position": 42.5})
    assert r.status_code == 200 and r.json()["progress"] == 42.5
    detail = client.get(f"/api/media/{mid}").json()
    assert detail["extra"]["progress"] == 42.5
    bf = client.post("/api/media/backfill-assets")
    assert bf.status_code == 200 and "updated" in bf.json()
    client.delete(f"/api/media/{mid}")


def test_access_token_guard(client):
    """回归：设置令牌后 API 返回 401，携带令牌/查询参数可通过，health 豁免。"""
    try:
        assert client.put("/api/settings", json={"access_token": "test-token-123"}).status_code == 200
        assert client.get("/api/novels").status_code == 401
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/novels", headers={"X-MoRead-Token": "test-token-123"}).status_code == 200
        assert client.get("/api/novels?token=test-token-123").status_code == 200
        assert client.get("/api/novels?token=wrong").status_code == 401
    finally:
        # 清理请求本身也需要携带令牌（守卫已启用）
        client.put("/api/settings", json={"access_token": ""},
                   headers={"X-MoRead-Token": "test-token-123"})
    assert client.get("/api/novels").status_code == 200
