"""A3 健康检查拆分：liveness 与 readiness 分离，readiness 报告组件状态。"""


def test_liveness_unconditional(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_readiness_reports_components(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": True, "data_dir": True}


def test_readiness_skips_token_guard(client):
    """配置了访问令牌时，探针端点仍可被编排层直接访问。"""
    try:
        assert client.put("/api/settings", json={"access_token": "probe-token"}).status_code == 200
        assert client.get("/api/novels").status_code == 401
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        client.put("/api/settings", json={"access_token": ""},
                   headers={"X-MoRead-Token": "probe-token"})
