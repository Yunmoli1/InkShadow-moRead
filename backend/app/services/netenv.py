"""Network environment: one place that decides how MoRead reaches the internet.

MoRead schedules external downloaders (Go/Python/Java) plus its own httpx
clients, so the proxy choice must be applied consistently in two places:

- ``get_proxy_url()``: resolve the effective proxy. Priority: settings DB
  ``proxy_url`` > ``MOREAD_PROXY`` / system ``HTTP(S)_PROXY`` env. Empty means
  direct connection.
- ``proxy_env()``: env vars injected into download-tool subprocesses so every
  tool routes through the same proxy. ``NO_PROXY`` always covers localhost so
  a local Ollama instance keeps working.
"""
from __future__ import annotations

import os

from ..database import SessionLocal
from ..models import Setting


async def get_proxy_url() -> str:
    async with SessionLocal() as db:
        row = await db.get(Setting, "proxy_url")
        proxy = (row.value if row else "") or ""
    proxy = proxy.strip()
    if proxy:
        return proxy
    for key in ("MOREAD_PROXY", "https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def proxy_env(proxy: str) -> dict[str, str]:
    """Env vars for download-tool subprocesses (all case variants, because
    different tools check different ones)."""
    if not proxy:
        return {}
    env: dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env[key] = proxy
    env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1"
    return env


def should_proxy(url: str, proxy: str) -> bool:
    """httpx clients: proxy remote URLs only, never loopback (local Ollama)."""
    if not proxy:
        return False
    host = (url.split("//", 1)[-1].split("/", 1)[0]).split("@")[-1]
    host = host.split(":")[0].strip("[]").lower()
    return host not in ("localhost", "127.0.0.1", "::1")
