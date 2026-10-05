"""Minimal systemd sd_notify client (A3).

Enables `WatchdogSec=` in the provided unit template: sends READY=1 once the
app is up and pings WATCHDOG=1 at half the watchdog interval. No-op when the
process isn't run under systemd (NOTIFY_SOCKET unset).
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket

log = logging.getLogger("moread.sdnotify")


def _socket() -> socket.socket | None:
    addr = os.environ.get("NOTIFY_SOCKET", "")
    if not addr:
        return None
    if addr.startswith("@"):  # abstract namespace socket
        addr = "\0" + addr[1:]
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)  # type: ignore[attr-defined]
    s.setblocking(False)
    s.connect(addr)
    return s


async def _send(msg: str) -> None:
    try:
        s = _socket()
        if s is None:
            return
        await asyncio.to_thread(s.send, msg.encode())
    except OSError as exc:
        log.debug("sd_notify failed: %s", exc)


async def ready() -> None:
    await _send("READY=1")


async def _watchdog_loop() -> None:
    usec = int(os.environ.get("WATCHDOG_USEC", "30000000"))
    interval = max(1.0, usec / 1e6 / 2)
    while True:
        await _send("WATCHDOG=1")
        await asyncio.sleep(interval)


def start_watchdog() -> asyncio.Task | None:
    """Return a watchdog ping task, or None when not under systemd."""
    if not os.environ.get("NOTIFY_SOCKET"):
        return None
    return asyncio.create_task(_watchdog_loop())
