"""Media asset generation: video duration & thumbnail, image thumbnail.

ffmpeg/ffprobe resolved from tools/ffmpeg/ (gitignored local dir) or PATH.
All calls are blocking subprocesses — callers must wrap in asyncio.to_thread.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .. import config

_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW on Windows


def _exe(dir_hint: str | None, name: str) -> Path | None:
    if dir_hint:
        d = Path(dir_hint)
        for cand in (d / f"{name}.exe", d / name):
            if cand.exists():
                return cand
    w = shutil.which(name)
    return Path(w) if w else None


def ffmpeg_exe() -> Path | None:
    from .tool_registry import ffmpeg_dir

    return _exe(ffmpeg_dir(), "ffmpeg")


def ffprobe_exe() -> Path | None:
    from .tool_registry import ffmpeg_dir

    return _exe(ffmpeg_dir(), "ffprobe")


def probe_duration(path: Path) -> float:
    """媒体时长（秒）；失败返回 0。"""
    ffprobe = ffprobe_exe()
    if not ffprobe:
        return 0.0
    try:
        proc = subprocess.run(
            [str(ffprobe), "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, timeout=30, creationflags=_NO_WINDOW,
        )
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        return float(data.get("format", {}).get("duration", 0) or 0)
    except Exception:
        return 0.0


def video_thumb(path: Path, out: Path, at_sec: float = 1.0) -> bool:
    """视频首帧缩略图（480px 宽）。"""
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return False
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [str(ffmpeg), "-y", "-loglevel", "error", "-ss", str(at_sec),
             "-i", str(path), "-frames:v", "1", "-vf", "scale=480:-2", str(out)],
            timeout=60, capture_output=True, creationflags=_NO_WINDOW, check=True,
        )
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def image_thumb(path: Path, out: Path, max_side: int = 480) -> bool:
    """图片缩略图（最长边 480px，JPEG）。"""
    try:
        from PIL import Image

        im = Image.open(path)
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=82)
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False


async def fill_media_assets(db, m) -> bool:
    """为一个 MediaItem 补齐时长与缩略图（异步不阻塞事件循环）。需先 flush 拿到 id。"""
    import asyncio

    path = config.DATA_DIR / m.file_path
    if not path.is_file():
        return False
    changed = False
    if m.media_type == "video" and not m.duration:
        dur = await asyncio.to_thread(probe_duration, path)
        if dur > 0:
            m.duration = round(dur, 2)
            changed = True
    if m.media_type in ("video", "image") and not m.thumbnail_path:
        thumb_rel = f"media/thumbs/{m.id}.jpg"
        out = config.DATA_DIR / thumb_rel
        ok = await asyncio.to_thread(
            video_thumb if m.media_type == "video" else image_thumb, path, out,
        )
        if ok:
            m.thumbnail_path = thumb_rel
            changed = True
    return changed
