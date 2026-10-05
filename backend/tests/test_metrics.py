"""A5 /api/metrics：结构完整 + 任务聚合（含错误码分布）。"""
import time


def test_metrics_shape(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    m = r.json()
    assert set(m) >= {"window_days", "tasks", "sse", "library", "storage"}
    t = m["tasks"]
    assert {"by_status", "total", "completed", "failed", "success_rate",
            "avg_duration_sec", "fallback_count", "by_error_code"} <= set(t)
    assert m["window_days"] == 30
    assert {"novels", "chapters", "notes", "media"} <= set(m["library"])
    assert "task_subscriptions" in m["sse"]


def test_metrics_counts_reflect_tasks(client):
    """跑一个会失败的任务后，failed 计数与错误码分布应反映出来。"""
    r = client.post("/api/tools/item-fetch/download", json={
        "url": "https://127.0.0.1:9/nope.bin", "content_type": "file"})
    task_id = r.json()["task_id"]
    deadline = time.time() + 60
    while time.time() < deadline:
        if client.get(f"/api/tasks/{task_id}").json()["status"] in ("completed", "failed", "canceled"):
            break
        time.sleep(0.4)
    m = client.get("/api/metrics").json()
    assert m["tasks"]["failed"] >= 1
    assert m["tasks"]["by_error_code"].get("NETWORK_ERROR", 0) >= 1
    assert m["tasks"]["success_rate"] is not None and m["tasks"]["success_rate"] < 1
