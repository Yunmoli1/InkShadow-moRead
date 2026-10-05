"""B3 任务详情增强：完整日志镜像文件 + /log 端点 + same_tool 重试。"""
import time
import uuid

from app.database import SessionLocal
from app.models import DownloadTask
from app.services.task_manager import MirroredLog, TASK_LOGS_DIR


def test_mirrored_log_writes_file_and_redacts(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.task_manager.TASK_LOGS_DIR", tmp_path)
    ml = MirroredLog("t1", maxlen=3)
    ml.append("line one")
    ml.append("https://a.b/c?token=super-secret")
    ml.append("line three")
    ml.append("line four")  # 超过 maxlen：内存只留 3 行，文件应有 4 行
    ml.close()
    assert list(ml) == ["https://a.b/c?token=super-secret", "line three", "line four"]
    content = (tmp_path / "t1.log").read_text(encoding="utf-8")
    assert len(content.strip().splitlines()) == 4
    assert "super-secret" not in content and "token=***" in content
    assert "line one" in content


def _seed_failed_task(client) -> str:
    """跑一个必失败任务，产生镜像日志文件。"""
    r = client.post("/api/tools/item-fetch/download", json={
        "url": "https://127.0.0.1:9/nope.bin", "content_type": "file"})
    task_id = r.json()["task_id"]
    deadline = time.time() + 60
    while time.time() < deadline:
        if client.get(f"/api/tasks/{task_id}").json()["status"] in ("completed", "failed", "canceled"):
            break
        time.sleep(0.4)
    return task_id


def test_full_log_endpoint(client):
    task_id = _seed_failed_task(client)
    r = client.get(f"/api/tasks/{task_id}/log")
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == task_id
    assert isinstance(body["lines"], list) and len(body["lines"]) >= 1
    assert any("FAILED" in l or "下载失败" in l for l in body["lines"])


def test_full_log_404(client):
    assert client.get("/api/tasks/missing/log").status_code == 404


def test_retry_same_tool(client):
    task_id = _seed_failed_task(client)
    r = client.post(f"/api/tasks/{task_id}/retry", params={"same_tool": "true"})
    assert r.status_code == 200
    new_id = r.json()["task_id"]
    t = client.get(f"/api/tasks/{new_id}").json()
    # item-fetch 是内置工具，original_tool 应等于任务工具
    assert t["options"].get("original_tool") == t["tool"]
    assert t["retry_count"] == 1
    client.delete(f"/api/tasks/{new_id}")


def test_fallback_chain_in_task_out(client):
    task_id = _seed_failed_task(client)
    t = client.get(f"/api/tasks/{task_id}").json()
    assert "fallback_chain" in t
