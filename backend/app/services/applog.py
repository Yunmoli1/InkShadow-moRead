"""Structured JSON logging with size-based rotation and secret redaction.

Every line in data/logs/moread.log is one JSON object:
    {"ts": "...", "level": "INFO", "logger": "moread.tasks", "msg": "...",
     "task_id": "...", "tool": "...", ...}
Known extras (task_id / tool / phase / duration_ms / code) are lifted to the
top level so a failed task can be traced end-to-end with grep '"task_id"'.

Secrets (tokens, api keys, passwords, Authorization headers) are redacted
before anything is written. Task URLs keep their path but query secrets are
masked, e.g.  https://a.b/c?token=***.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .. import config

LOG_DIR = config.DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "moread.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

_SECRET_PARAM = re.compile(
    r"(?i)(token|access_token|api[_-]?key|apikey|key|secret|password|passwd|pwd|auth)"
    r"=([^&\s\"']+)")
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._\-]+")
_BASIC = re.compile(r"(?i)basic\s+[a-z0-9+/=]+")


def redact(text: str) -> str:
    """Mask credential-looking substrings (URL query params, headers)."""
    if not text:
        return text
    out = _SECRET_PARAM.sub(r"\1=***", text)
    out = _BEARER.sub("Bearer ***", out)
    out = _BASIC.sub("Basic ***", out)
    return out


_TOP_LEVEL_EXTRAS = ("task_id", "tool", "phase", "duration_ms", "code", "event")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        for key in _TOP_LEVEL_EXTRAS:
            v = record.__dict__.get(key)
            if v is not None:
                entry[key] = redact(v) if isinstance(v, str) else v
        # unexpected extras ride along under "extra"
        known = set(_TOP_LEVEL_EXTRAS) | set(
            ("name", "msg", "args", "levelname", "levelno", "pathname", "filename",
             "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
             "created", "msecs", "relativeCreated", "thread", "threadName",
             "processName", "process", "taskName", "message", "asctime"))
        rest = {k: v for k, v in record.__dict__.items()
                if k not in known and not k.startswith("_")}
        if rest:
            entry["extra"] = rest
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(entry, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps({"ts": entry.get("ts"), "level": entry["level"],
                               "logger": entry["logger"], "msg": "unserializable log entry"},
                              ensure_ascii=False)


_configured = False


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    """Install the rotating JSON file handler (idempotent).

    Also routes uvicorn's error log (startup/shutdown/tracebacks) into the
    same file; uvicorn.access stays console-only to avoid noise.
    """
    global _configured
    target = (log_dir or LOG_DIR)
    target.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        target / "moread.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    uv_err = logging.getLogger("uvicorn.error")
    uv_err.addHandler(handler)
    _configured = True


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"moread.{component}")
