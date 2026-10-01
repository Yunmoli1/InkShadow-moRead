"""Single-file executable entrypoint (PyInstaller).

Runs the FastAPI app with uvicorn and opens the browser. Data is written next
to the executable; the frontend build is read from the bundled resources.
Set MOREAD_NO_BROWSER=1 to skip auto-opening the browser.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

import uvicorn

from app.main import app

HOST = os.environ.get("MOREAD_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOREAD_PORT", "8686"))


def _open_browser(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def _port_in_use() -> bool:
    """True if something (likely another MoRead instance) already serves HTTP."""
    import urllib.request

    try:
        urllib.request.urlopen(f"http://{HOST}:{PORT}/api/settings", timeout=2)
        return True
    except Exception:
        return False


def _pause_before_exit() -> None:
    """Keep the console window open so double-click users can read the error."""
    if os.environ.get("MOREAD_NO_PAUSE"):
        return
    try:
        input("\n按回车键关闭窗口…")
    except EOFError:
        pass


def main() -> None:
    if _port_in_use():
        # A second launch while one instance is running: just open its page.
        print(f"墨读已在 http://{HOST}:{PORT} 运行，将打开已运行的实例。")
        webbrowser.open(f"http://{HOST}:{PORT}")
        time.sleep(1)
        return
    if not os.environ.get("MOREAD_NO_BROWSER"):
        threading.Thread(target=_open_browser, args=(f"http://{HOST}:{PORT}",), daemon=True).start()
    print(f"墨读 MoRead 正在运行: http://{HOST}:{PORT}  (Ctrl+C 退出)")
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    except OSError as exc:
        # Port taken between our probe and bind, or no HTTP service answered.
        print(f"\n启动失败：端口 {PORT} 无法绑定（{exc}）。")
        print("可能已有一个墨读实例在运行，请先关闭它，或用 MOREAD_PORT 指定其他端口。")
        _pause_before_exit()
        sys.exit(1)


if __name__ == "__main__":
    main()
