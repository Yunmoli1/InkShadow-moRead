"""Builtin webpage→novel converter (last-resort fallback for novel tasks).

Strategy:
1. Fetch the page and extract the main article text with trafilatura.
2. If the page is text-poor (image-based content, heavy JS), take a tall
   headless screenshot with Edge/Chrome and OCR it (RapidOCR, Chinese+EN).

The extracted text is written as a TXT book into the task dir; the regular
novel importer then picks it up (chapters are pre-split by heading patterns).
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from .netenv import get_proxy_url, should_proxy

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_MIN_TEXT = 300          # below this we assume image-based content and OCR
_SHOT_W, _SHOT_H = 1280, 12000


def find_browser() -> str | None:
    """A Chromium-family binary for headless screenshots (Edge ships with Windows)."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return shutil.which("msedge") or shutil.which("chrome")


def _ocr_image(path: str) -> list[str]:
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    result, _ = ocr(path)
    return [line[1].strip() for line in (result or []) if line[1].strip()]


def _run_shot(browser: str, png: Path, url: str, proxy: str | None,
              diag: list[str]) -> bool:
    profile = tempfile.mkdtemp(prefix="moread-shot-")
    try:
        base = [
            browser, f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", "--disable-sync",
            "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
            "--disable-extensions", "--mute-audio",
            f"--user-agent={_UA}",
            f"--window-size={_SHOT_W},{_SHOT_H}",
            f"--screenshot={png}",
        ]
        if proxy:
            base.append(f"--proxy-server={proxy}")
        # 旧版 Edge 不支持 --headless=new，两种模式都试一遍
        for headless in ("--headless=new", "--headless"):
            argv = [browser, headless, *base[1:], url]
            try:
                r = subprocess.run(argv, capture_output=True, timeout=180,
                                   creationflags=0x08000000)
                out = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")
                diag.append(f"mode={headless[2:]} rc={r.returncode} out={out.strip()[-120:]}")
            except subprocess.TimeoutExpired:
                diag.append(f"mode={headless[2:]} 超时(180s)")
            if png.exists():
                return True
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _screenshot_and_ocr(url: str, png_path: str, proxy: str,
                        log_lines: list[str] | None = None) -> str:
    browser = find_browser()
    if not browser:
        raise RuntimeError("未找到 Edge/Chrome，无法对图片化页面进行截图 OCR")
    png = Path(png_path)
    diag: list[str] = []
    # 有代理先走代理；直连始终兜底再试一轮（代理失效时直连往往反而可达）
    attempts: list[str | None] = [proxy] if proxy else []
    attempts.append(None)
    ok = False
    for p in attempts:
        tag = f"via proxy {p}" if p else "direct"
        if log_lines is not None:
            log_lines.append(f"screenshot attempt: {tag}")
        ok = _run_shot(browser, png, url, p, diag)
        if log_lines is not None:
            log_lines.extend(f"  {d}" for d in diag[-2:])
        if ok:
            break
        png.unlink(missing_ok=True)
    if not ok:
        raise RuntimeError(
            "页面截图失败：无头浏览器未产出图片。尝试详情: " + " || ".join(diag[-2:]))
    lines = _ocr_image(png_path)
    return "\n".join(lines)


async def save_web_novel(url: str, out_dir: str) -> AsyncIterator[dict]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    yield {"progress": 5, "message": "抓取网页…", "log": f"GET {url}"}
    proxy = await get_proxy_url()
    async with httpx.AsyncClient(follow_redirects=True, timeout=45, headers={
        "User-Agent": _UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }, proxy=proxy if should_proxy(url, proxy) else None) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    yield {"progress": 30, "message": "提取正文…"}
    text = ""
    title = ""
    try:
        import trafilatura

        text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        meta = trafilatura.extract_metadata(html)
        title = (meta.title if meta and meta.title else "")[:80]
    except Exception:
        text = ""

    if len(text.strip()) < _MIN_TEXT:
        yield {"progress": 55, "message": "正文过少，改用截图 OCR…", "log": "text too short, OCR fallback"}
        png = str(Path(out_dir) / "page_shot.png")
        shot_log: list[str] = []
        try:
            text = await asyncio.to_thread(_screenshot_and_ocr, url, png, proxy, shot_log)
        except Exception as exc:
            for line in shot_log:
                yield {"log": line}
            raise
        if len(text.strip()) < 20:
            raise RuntimeError("未能从页面提取到文字（站点可能需要代理或内容为纯图片）")

    safe_title = re.sub(r'[\\/:*?"<>|\r\n]+', "_", title or url.rsplit("/", 1)[-1] or "网页小说")[:50] or "网页小说"
    body = f"{safe_title}\n\n{text.strip()}\n"
    f = Path(out_dir) / f"{safe_title}.txt"
    f.write_text(body, encoding="utf-8")
    yield {"progress": 95, "message": f"已生成 {f.name}", "log": f"saved: {f.name}"}
