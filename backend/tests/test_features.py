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
    novel = client.get("/api/novels", params={"search": "大书备份测试"}).json()["items"][0]
    nid = novel["id"]

    exp = client.get("/api/backup/export")
    payload = exp.json()
    assert payload["version"] == 3
    book = next(b for b in payload["novels"] if b["title"] == "大书备份测试")
    assert sum(len(c["content"]) for c in book["chapters"]) > 2 * 1024 * 1024, "大书正文应被内联"
    assert client.delete(f"/api/novels/{nid}").status_code == 200
    imp = client.post("/api/backup/import", json=payload)
    assert imp.status_code == 200 and imp.json()["restored_novels"] >= 1
    restored = client.get("/api/novels", params={"search": "大书备份测试"}).json()["items"][0]
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
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
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
    media = client.get("/api/media", params={"media_type": "image"}).json()["items"][0]
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


def test_backup_notes_roundtrip(client):
    """回归（评审 6.1）：备份跨实例恢复后笔记通过 backup_id 重映射不丢失；
    已存在同书时笔记也应挂到现有书上且不重复。"""
    r = client.post("/api/novels/import", files=[
        ("files", (f"nt_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200
    novel = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
    nid = novel["id"]
    note = client.post(f"/api/novels/{nid}/notes", json={
        "chapter_idx": 1, "chapter_title": "第2章 测试章节",
        "excerpt": "回归摘录", "content": "跨实例笔记回归",
    })
    assert note.status_code == 201

    payload = client.get("/api/backup/export").json()
    assert payload["version"] == 3 and payload["novels"][0].get("backup_id")

    # 场景 A：删除后全新实例恢复
    assert client.delete(f"/api/novels/{nid}").status_code == 200
    imp = client.post("/api/backup/import", json=payload).json()
    assert imp["restored_novels"] == 1 and imp["restored_notes"] == 1, imp
    restored = client.get("/api/novels", params={"search": "测试之书"}).json()["items"][0]
    assert restored["id"] != nid  # 新 UUID
    notes = client.get(f"/api/novels/{restored['id']}/notes").json()
    assert len(notes) == 1 and notes[0]["content"] == "跨实例笔记回归"
    assert notes[0]["chapter_idx"] == 1

    # 场景 B：再次导入同备份 → 书已存在，笔记映射到现有书但不重复创建
    imp2 = client.post("/api/backup/import", json=payload).json()
    assert imp2["restored_novels"] == 0
    notes2 = client.get(f"/api/novels/{restored['id']}/notes").json()
    assert len(notes2) == 1, "重复导入不应产生重复笔记"
    assert client.delete(f"/api/novels/{restored['id']}").status_code == 200


def test_task_options_persist_and_retry(client):
    """回归（评审 6.2）：任务 options 持久化，重试复制原参数。"""
    # builtin 页面任务带自定义 options
    r = client.post("/api/tools/builtin-web-saver/download", json={
        "url": "https://example.com/options-test", "options": {"marker": "keep-me"},
    })
    assert r.status_code == 201
    tid = r.json()["task_id"]
    task = client.get(f"/api/tasks/{tid}").json()
    # B3 起系统会注入 original_tool；断言自定义 options 被完整保留即可
    assert task["options"].get("marker") == "keep-me", task.get("options")

    # 失败/完成的任务可重试 → 新任务保留 url/options
    deadline = __import__("time").time() + 30
    while __import__("time").time() < deadline:
        st = client.get(f"/api/tasks/{tid}").json()["status"]
        if st in ("completed", "failed"):
            break
        __import__("time").sleep(0.3)
    client.delete(f"/api/tasks/{tid}")
    # 用已结束任务验证 retry：重新创建一个并手动走完
    r2 = client.post("/api/tools/builtin-web-saver/download", json={
        "url": "https://example.com/options-test-2", "options": {"marker": "retry-me"},
    })
    tid2 = r2.json()["task_id"]
    deadline = __import__("time").time() + 30
    while __import__("time").time() < deadline:
        st = client.get(f"/api/tasks/{tid2}").json()["status"]
        if st in ("completed", "failed"):
            break
        __import__("time").sleep(0.3)
    retry = client.post(f"/api/tasks/{tid2}/retry")
    assert retry.status_code == 200, retry.text
    new_id = retry.json()["task_id"]
    assert new_id != tid2
    new_task = client.get(f"/api/tasks/{new_id}").json()
    assert new_task["options"].get("marker") == "retry-me"
    assert new_task["url"] == "https://example.com/options-test-2"
    # 不可重试：running/queued/completed 状态
    assert client.post(f"/api/tasks/{new_id}/retry").status_code in (400,)
    for x in (tid2, new_id):
        deadline = __import__("time").time() + 30
        while __import__("time").time() < deadline:
            if client.get(f"/api/tasks/{x}").json()["status"] in ("completed", "failed"):
                break
            __import__("time").sleep(0.3)
        client.delete(f"/api/tasks/{x}")


def test_article_extraction_unit(client):
    """正文提取单元级验证：噪声页能抽出干净正文。"""
    import asyncio

    from app.services.article_extractor import extract_article

    html = (
        "<html><head><title>测试文章标题</title></head><body>"
        "<nav>首页 分类 关于 登录</nav>"
        "<article><h1>测试文章标题</h1>"
        "<p>" + "这是一段足够长的正文内容，用来验证 readability 提取算法。" * 30 + "</p>"
        "</article>"
        "<footer>版权所有 广告位</footer>"
        "</body></html>"
    )
    result = extract_article(html)
    assert result is not None
    assert "readability 提取算法" in result["text"]
    assert "首页 分类" not in result["text"]
    assert "广告位" not in result["text"]

    # 导航页/登录墙 → None
    assert extract_article("<html><body><a href=/x>登录</a></body></html>") is None
    _ = asyncio  # noqa


def test_extract_article_from_media_api(client):
    """回归：网页归档 -> 提取正文 -> 文章进书架且阅读器可读。"""
    body = "这是一篇关于本地优先知识库的长文章。" * 60
    html = (
        "<html><head><title>本地优先知识库漫谈</title></head><body>"
        "<nav>导航 首页 关于</nav><article><p>" + body + "</p></article></body></html>"
    ).encode("utf-8")
    r = client.post("/api/media/batch-import", files=[
        ("files", ("article.html", html, "text/html")),
    ])
    assert r.status_code == 201
    page = client.get("/api/media", params={"media_type": "page"}).json()["items"][0]

    res = client.post(f"/api/media/{page['id']}/extract-article")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "本地优先知识库" in data["title"]

    novels = client.get("/api/novels", params={"search": "本地优先知识库漫谈"}).json()["items"]
    assert len(novels) == 1
    novel = novels[0]
    assert novel["category"] == "文章" and novel["total_chapters"] == 1
    chapters = client.get(f"/api/novels/{novel['id']}/chapters").json()
    content = client.get(
        f"/api/novels/{novel['id']}/chapters/{chapters['items'][0]['id']}/content"
    ).json()
    assert "本地优先知识库" in content["content"] and "导航 首页" not in content["content"]

    res2 = client.post(f"/api/media/{page['id']}/extract-article").json()
    assert res2["novel_id"] == novel["id"]

    png = b"PNG" + bytes([0x0d, 0x0a, 0x1a]) + bytes(50)
    client.post("/api/media/batch-import", files=[("files", ("x.png", png, "image/png"))])
    img = client.get("/api/media", params={"media_type": "image"}).json()["items"][0]
    assert client.post(f"/api/media/{img['id']}/extract-article").status_code == 400

    client.delete(f"/api/novels/{novel['id']}")
    client.delete(f"/api/media/{page['id']}")
    client.delete(f"/api/media/{img['id']}")


