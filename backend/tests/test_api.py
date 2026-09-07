"""End-to-end API tests covering the full acceptance surface.

Run: cd backend && python -m pytest tests/ -v
"""
import time
import uuid

import pytest

OK = [200, 201]


# ---------------------------------------------------------------------------
# meta / settings / storage / search
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_openapi_docs(client):
    r = client.get("/openapi.json")
    paths = r.json()["paths"]
    assert r.status_code == 200
    for p in ["/api/tools", "/api/tasks", "/api/novels", "/api/media",
              "/api/settings", "/api/backup/export", "/api/search", "/api/novels/stats"]:
        assert p in paths, f"missing {p}"


def test_settings_roundtrip(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "ai_base_url" in data and "storage_quota_gb" in data
    r2 = client.put("/api/settings", json={"ai_model": "llama3", "storage_quota_gb": 30})
    assert r2.status_code == 200 and r2.json()["storage_quota_gb"] == 30


def test_storage_stats_and_cleanup(client):
    r = client.get("/api/storage/stats")
    assert r.status_code == 200
    assert {"used_bytes", "quota_bytes", "percent", "novels_bytes"} <= set(r.json())
    r2 = client.post("/api/storage/cleanup?older_than_days=0")
    assert r2.status_code == 200 and "removed" in r2.json()


def test_global_search(client):
    r = client.get("/api/search", params={"q": ""})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

def test_tools_list(client):
    r = client.get("/api/tools")
    tools = r.json()
    assert r.status_code == 200 and len(tools) >= 13
    by_name = {t["name"]: t for t in tools}
    for expected in ("yt-dlp", "gallery-dl", "lncrawl", "builtin-web-saver", "archivebox"):
        assert expected in by_name
    # builtin is always installed
    assert by_name["builtin-web-saver"]["installed"] is True
    for t in tools:
        assert {"name", "installed", "install_hint", "content_types"} <= set(t)


def test_search_with_uninstalled_tool_friendly_error(client):
    # FictionDown is not installed in test env -> friendly 400, not crash
    r = client.post("/api/tools/FictionDown/search", json={"query": "x"})
    assert r.status_code == 400
    assert "未安装" in r.json()["detail"]


def test_unknown_tool_404(client):
    r = client.post("/api/tools/no-such-tool/search", json={"query": "x"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# universal grab flow: builtin page saver -> SSE -> media -> delete
# ---------------------------------------------------------------------------

def _wait_task(client, task_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = client.get(f"/api/tasks/{task_id}").json()
        if t["status"] in ("completed", "failed", "canceled"):
            return t
        time.sleep(0.4)
    return t


def test_grab_page_flow(client):
    # create download (auto pick: page -> builtin-web-saver)
    r = client.post("/api/tools/auto/download", json={
        "url": "https://example.com", "content_type": "page",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["task_id"] and data["status"] in ("queued", "running")

    # SSE stream should produce snapshot + end
    with client.stream("GET", f"/api/tasks/{data['task_id']}/status") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = b"".join(chunk for chunk in resp.iter_bytes()).decode("utf-8", "replace")
        assert "event: snapshot" in body
        assert "event: end" in body

    task = _wait_task(client, data["task_id"])
    assert task["status"] == "completed", task["message"]

    # media library has the page archive
    r = client.get("/api/media", params={"media_type": "page"})
    items = r.json()
    assert len(items) >= 1
    item = items[0]
    assert item["preview_url"].startswith("/api/media/")
    # file serving with Range (video/audio streaming contract)
    fr = client.get(item["preview_url"], headers={"Range": "bytes=0-9"})
    assert fr.status_code in (200, 206)
    if fr.status_code == 206:
        assert fr.headers["content-range"].startswith("bytes 0-9/")
        assert len(fr.content) == 10


def test_media_batch_import_and_delete(client):
    files = [
        ("files", ("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")),
        ("files", ("b.txt", b"not media", "text/plain")),
    ]
    r = client.post("/api/media/batch-import", files=files)
    assert r.status_code == 201
    data = r.json()
    assert data["count"] == 1 and data["skipped"] == ["b.txt"]
    media_id = client.get("/api/media", params={"media_type": "image"}).json()[0]["id"]
    detail = client.get(f"/api/media/{media_id}")
    assert detail.status_code == 200 and detail.json()["media_type"] == "image"
    assert client.delete(f"/api/media/{media_id}").status_code == 200
    assert client.get(f"/api/media/{media_id}").status_code == 404


# ---------------------------------------------------------------------------
# novels: import -> shelf -> chapters -> notes -> progress -> stats
# ---------------------------------------------------------------------------

def _make_novel_txt(n_chapters=5):
    parts = []
    for i in range(1, n_chapters + 1):
        parts.append(f"第{i}章 测试章节")
        parts.append("这是测试正文内容，用于验证章节解析流程是否正常工作。" * 8)
    return ("测试之书\n\n" + "\n\n".join(parts)).encode("utf-8")


def test_novel_full_flow(client):
    # import
    r = client.post("/api/novels/import", files=[
        ("files", (f"novel_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(), "text/plain")),
    ])
    assert r.status_code == 200
    res = r.json()
    assert len(res["imported"]) == 1 and not res["errors"]

    # shelf list + search + detail
    novels = client.get("/api/novels", params={"search": "测试之书"}).json()
    assert len(novels) == 1
    novel = novels[0]
    nid = novel["id"]
    assert novel["total_chapters"] == 5
    detail = client.get(f"/api/novels/{nid}")
    assert detail.status_code == 200 and detail.json()["id"] == nid

    # chapters pagination (virtual scroll backing API)
    page = client.get(f"/api/novels/{nid}/chapters", params={"offset": 0, "limit": 2})
    body = page.json()
    assert body["total"] == 5 and len(body["items"]) == 2
    rest = client.get(f"/api/novels/{nid}/chapters", params={"offset": 2, "limit": 500}).json()
    assert len(rest["items"]) == 3

    # content
    cid = body["items"][0]["id"]
    content = client.get(f"/api/novels/{nid}/chapters/{cid}/content").json()
    assert content["title"].startswith("第1章")
    assert len(content["content"]) > 50

    # progress + reading session
    r = client.patch(f"/api/novels/{nid}/progress", json={
        "chapter_idx": 2, "scroll_pos": 0.5, "duration_sec": 120, "chapters_read": 1,
    })
    assert r.status_code == 200 and r.json()["read_chapters"] == 3

    # notes CRUD
    note = client.post(f"/api/novels/{nid}/notes", json={
        "chapter_id": cid, "chapter_title": content["title"], "chapter_idx": 0,
        "excerpt": "测试批注", "content": "这是一条笔记",
    })
    assert note.status_code == 201
    note_id = note.json()["id"]
    notes = client.get(f"/api/novels/{nid}/notes", params={"chapter_idx": 0}).json()
    assert len(notes) == 1
    assert client.delete(f"/api/novels/{nid}/notes/{note_id}").status_code == 200

    # stats reflects reading
    stats = client.get("/api/novels/stats").json()
    assert stats["total_novels"] >= 1 and stats["total_minutes"] >= 2

    # AI summary friendly failure (no Ollama in test env) -> 503, app not crashed
    ai = client.post(f"/api/novels/{nid}/ai-summary", json={"chapter_id": cid})
    assert ai.status_code in (503, 400)

    # delete novel cascades
    assert client.delete(f"/api/novels/{nid}").status_code == 200
    assert client.get(f"/api/novels/{nid}").status_code == 404


def test_novel_import_rejects_bad_type(client):
    r = client.post("/api/novels/import", files=[
        ("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf")),
    ])
    assert r.status_code == 200
    res = r.json()
    assert res["skipped"] == ["x.pdf"]


def test_novel_404(client):
    assert client.get("/api/novels/does-not-exist").status_code == 404


# ---------------------------------------------------------------------------
# tasks lifecycle
# ---------------------------------------------------------------------------

def test_tasks_list_and_validation(client):
    r = client.get("/api/tasks", params={"page": 1, "page_size": 5})
    assert r.status_code == 200
    assert {"items", "total", "page", "page_size"} <= set(r.json())
    # resume of non-paused task -> 400
    tasks = client.get("/api/tasks").json()["items"]
    if tasks:
        tid = tasks[0]["id"]
        assert client.post(f"/api/tasks/{tid}/resume").status_code == 400
    assert client.delete("/api/tasks/no-such-task").status_code == 404


def test_pause_resume_roundtrip(client):
    # long-ish builtin task; pause mid-flight if possible, then cancel+delete
    r = client.post("/api/tools/builtin-web-saver/download", json={"url": "https://example.com"})
    tid = r.json()["task_id"]
    t = client.get(f"/api/tasks/{tid}").json()
    if t["status"] == "running":
        assert client.post(f"/api/tasks/{tid}/pause").json()["status"] == "paused"
        assert client.post(f"/api/tasks/{tid}/resume").json()["status"] == "queued"
    t = _wait_task(client, tid)
    assert t["status"] in ("completed", "canceled")
    assert client.delete(f"/api/tasks/{tid}").status_code == 200


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

def test_backup_export_import(client):
    # seed one novel
    client.post("/api/novels/import", files=[
        ("files", (f"bk_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    exp = client.get("/api/backup/export")
    assert exp.status_code == 200
    payload = exp.json()
    assert payload["app"] == "MoRead"
    assert isinstance(payload["novels"], list)
    assert client.post("/api/backup/import", json=payload).status_code == 200
    bad = client.post("/api/backup/import", json={"app": "other"})
    assert bad.status_code == 400
