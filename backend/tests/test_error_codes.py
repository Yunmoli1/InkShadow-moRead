"""A2 错误分类码：分类规则 + 失败任务落库 + API 暴露。"""
import time

from app.services.error_codes import classify_failure, classify_text


def test_classify_auth():
    assert classify_failure(1, "HTTP Error 403: Forbidden") == "AUTH_REQUIRED"
    assert classify_text("login required to view this chapter") == "AUTH_REQUIRED"


def test_classify_network():
    assert classify_text("getaddrinfo failed") == "NETWORK_ERROR"
    assert classify_text("ConnectionRefusedError: [Errno 111] Connection refused") == "NETWORK_ERROR"
    assert classify_text("All connection attempts failed") == "NETWORK_ERROR"
    assert classify_text("由于目标计算机积极拒绝，无法连接。") == "NETWORK_ERROR"
    assert classify_failure(1, "urllib3 ReadTimeoutError") == "NETWORK_ERROR"


def test_classify_no_content_and_spawn():
    assert classify_failure(1, "HTTP Error 404: Not Found") == "NO_CONTENT"
    assert classify_text("'yt-dlp' is not recognized as an internal or external command") == "SPAWN_ERROR"


def test_classify_zero_rc_is_empty():
    assert classify_failure(0) == ""


def test_classify_unknown_falls_back():
    assert classify_failure(1, "随机输出 xyz") == "UNKNOWN"


def test_failed_task_carries_error_code(client):
    """item-fetch 打不可路由端口 → NETWORK_ERROR 分类落库并在 API 返回。"""
    r = client.post("/api/tools/item-fetch/download", json={
        "url": "https://127.0.0.1:9/unreachable.bin", "content_type": "file",
    })
    assert r.status_code == 201
    task_id = r.json()["task_id"]
    deadline = time.time() + 60
    task = {}
    while time.time() < deadline:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] in ("completed", "failed", "canceled"):
            break
        time.sleep(0.4)
    assert task["status"] == "failed"
    assert task["error_code"] == "NETWORK_ERROR"
    assert "error_code" in task and "retry_count" in task
