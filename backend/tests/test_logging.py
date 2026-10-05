"""A1 结构化日志：JSON 格式、task_id 追溯、脱敏、大小轮转配置。"""
import json
import logging

from app.services import applog
from app.services.applog import redact, setup_logging


def test_redact_masks_query_secrets():
    url = "https://example.com/video?token=abc123&q=x"
    out = redact(url)
    assert "abc123" not in out
    assert "token=***" in out
    assert "q=x" in out  # 非敏感参数保留


def test_redact_masks_headers_and_keys():
    assert "Bearer ***" in redact("Authorization: Bearer eyJhbGciOi.abc")
    assert "Basic ***" in redact("Authorization: Basic dXNlcjpwYXNz")
    assert "api_key=***" in redact("https://a.b?f?api_key=sk-1234567890")
    assert "password=***" in redact("login?password=hunter2")


def test_redact_keeps_normal_text():
    assert redact("普通中文日志 & https://example.com/path") == "普通中文日志 & https://example.com/path"


def test_json_log_writes_task_id(tmp_path, monkeypatch):
    monkeypatch.setattr(applog, "_configured", False)
    setup_logging(log_dir=tmp_path)
    log = applog.get_logger("test")
    log.info("task created: https://a.b/c?token=secret", extra={
        "event": "create", "task_id": "t123", "tool": "yt-dlp"})
    log.warning("exit %d", 1, extra={"task_id": "t123", "duration_ms": 1500})
    # 清理：移除 handler，避免污染其他测试
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, logging.handlers.RotatingFileHandler):
            root.removeHandler(h)
            h.close()

    lines = (tmp_path / "moread.log").read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(l) for l in lines]
    by_event = {e.get("event"): e for e in entries}
    created = by_event["create"]
    assert created["task_id"] == "t123"
    assert created["tool"] == "yt-dlp"
    assert "secret" not in created["msg"]
    assert "token=***" in created["msg"]
    finished = [e for e in entries if e.get("duration_ms") == 1500][0]
    assert finished["level"] == "WARNING"
    assert finished["task_id"] == "t123"


def test_setup_logging_rotation_params(tmp_path, monkeypatch):
    """验证轮转参数：5MB × 5 个备份（大小轮转而非时间轮转）。"""
    import logging.handlers
    monkeypatch.setattr(applog, "_configured", False)
    setup_logging(log_dir=tmp_path)
    handlers = [h for h in logging.getLogger().handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)]
    # 清理
    for h in handlers:
        logging.getLogger().removeHandler(h)
        h.close()
    assert handlers, "应安装 RotatingFileHandler"
    h = handlers[-1]
    assert h.maxBytes == 5 * 1024 * 1024
    assert h.backupCount == 5
