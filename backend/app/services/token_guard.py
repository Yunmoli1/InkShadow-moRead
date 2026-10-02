"""访问令牌缓存：/api 请求守卫用。设置变更时调用 invalidate()。"""
from __future__ import annotations

import asyncio
import time

_cache = {"value": None, "expires": 0.0}


def invalidate() -> None:
    """access_token 变更后调用，立即生效。"""
    _cache["expires"] = 0.0
    _cache["value"] = None


async def current_token() -> str:
    """读取当前令牌（5 秒 TTL 缓存；空串表示未启用）。"""
    now = time.monotonic()
    if now < _cache["expires"]:
        return _cache["value"] or ""
    from ..database import SessionLocal
    from ..models import Setting

    await asyncio.sleep(0)
    async with SessionLocal() as db:
        row = await db.get(Setting, "access_token")
    token = str(row.value or "") if row else ""
    _cache["value"] = token
    _cache["expires"] = now + 5.0
    return token
