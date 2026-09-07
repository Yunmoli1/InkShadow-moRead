"""Tool registry: definitions, availability detection, argv builders, progress parsers.

This is the heart of the "tool scheduling" architecture: MoRead never crawls by
itself -- it schedules professional open-source downloaders found on PATH.
"""
from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    name: str
    display: str
    category: str                    # universal / video / audio / image / novel / page
    executables: list[str] = field(default_factory=list)
    version_args: list[str] = field(default_factory=lambda: ["--version"])
    version_regex: str = r"(\d+[\w.\-+]*)"
    install_hint: str = ""
    supports_search: bool = False
    content_types: list[str] = field(default_factory=list)   # auto/image/video/audio/page/novel
    resume_mode: str = "rerun"       # rerun (tool continues from partials) | none
    docs_url: str = ""
    remark: str = ""


REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name="yt-dlp", display="yt-dlp", category="video",
            executables=["yt-dlp", "yt-dlp.exe"],
            supports_search=True, content_types=["video", "audio"],
            install_hint="pip install yt-dlp",
            docs_url="https://github.com/yt-dlp/yt-dlp",
            remark="视频/音频专项，支持 1000+ 网站，支持断点续传",
        ),
        ToolSpec(
            name="you-get", display="you-get", category="video",
            executables=["you-get", "you-get.exe"],
            content_types=["video", "audio"],
            install_hint="pip install you-get",
            docs_url="https://github.com/soimort/you-get",
            remark="视频/音频专项，国内站点支持较好",
        ),
        ToolSpec(
            name="gallery-dl", display="gallery-dl", category="image",
            executables=["gallery-dl", "gallery-dl.exe"],
            content_types=["image"],
            install_hint="pip install gallery-dl",
            docs_url="https://github.com/mikf/gallery-dl",
            remark="图片专项，支持 1400+ 网站（图站/相册）",
        ),
        ToolSpec(
            name="lncrawl", display="Lightnovel Crawler", category="novel",
            executables=["lncrawl", "lncrawl.exe"],
            version_args=["version"], version_regex=r"v(\d+[\w.\-+]*)",
            supports_search=True, content_types=["novel"],
            install_hint="pip install -U lightnovel-crawler",
            docs_url="https://github.com/dipu-bd/lightnovel-crawler",
            resume_mode="rerun",
            remark="小说专项，支持数百个小说站，输出 TXT/EPUB，支持断点续传",
        ),
        ToolSpec(
            name="novel-downloader", display="Novel Downloader", category="novel",
            executables=["novel-downloader", "novel-downloader.exe"],
            content_types=["novel"],
            install_hint="pip install novel-downloader",
            docs_url="https://github.com/solidSpoon/DSPtool",
            remark="小说专项下载器",
        ),
        ToolSpec(
            name="FictionDown", display="FictionDown", category="novel",
            executables=["FictionDown", "FictionDown.exe"],
            content_types=["novel"],
            install_hint="从 GitHub Releases 下载：github.com/ma6254/FictionDown",
            docs_url="https://github.com/ma6254/FictionDown",
            remark="小说专项（起点/笔趣阁等），单二进制",
        ),
        ToolSpec(
            name="so-novel", display="So Novel", category="novel",
            executables=["so-novel", "so-novel.exe"],
            content_types=["novel"],
            install_hint="从 GitHub Releases 下载：github.com/javPower/so-novel",
            docs_url="https://github.com/javPower/so-novel",
            remark="小说专项聚合下载器，需 Java 11+",
        ),
        ToolSpec(
            name="abx-dl", display="abx-dl", category="universal",
            executables=["abx-dl", "abx-dl.exe"],
            content_types=["auto", "image", "video", "audio", "page"],
            install_hint="pip install abx-dl",
            docs_url="https://github.com/ArchiveBox/abx",
            remark="多媒体全能下载器（ArchiveBox 生态），自动识别 HTML/图片/视频/音频",
        ),
        ToolSpec(
            name="DXC", display="DXC", category="universal",
            executables=["DXC", "DXC.exe", "dxc"],
            content_types=["auto", "image", "video", "audio"],
            install_hint="从项目 Releases 下载 DXC 可执行文件",
            remark="多媒体全能下载器，自动检测并下载 URL 中的内容",
        ),
        ToolSpec(
            name="vget", display="vget", category="universal",
            executables=["vget", "vget.exe"],
            content_types=["auto", "image", "video", "audio"],
            install_hint="从项目 Releases 下载 vget 可执行文件",
            remark="多媒体全能下载器",
        ),
        ToolSpec(
            name="pull-vids", display="pull-vids", category="video",
            executables=["pull-vids", "pull-vids.exe"],
            content_types=["video"],
            install_hint="从项目 Releases 下载 pull-vids 可执行文件",
            remark="视频批量拉取工具",
        ),
        ToolSpec(
            name="image-harvest", display="Image Harvest", category="image",
            executables=["image-harvest", "image-harvest.exe", "ih"],
            content_types=["image"],
            install_hint="从项目 Releases 下载 image-harvest 可执行文件",
            remark="图片批量采集工具",
        ),
        ToolSpec(
            name="archivebox", display="ArchiveBox", category="page",
            executables=["archivebox", "archivebox.exe"],
            version_args=["version"],
            content_types=["page"],
            install_hint="docker run -v $PWD/data:/data archivebox/archivebox  或  pip install archivebox",
            docs_url="https://github.com/ArchiveBox/ArchiveBox",
            remark="网页完整归档：HTML / PDF / PNG 截图",
        ),
        ToolSpec(
            name="builtin-web-saver", display="内置单页快照", category="page",
            executables=[],                     # no external binary; python built-in
            content_types=["page"],
            install_hint="无需安装（内置兜底）",
            remark="兜底方案：仅抓取单个网页 HTML 存档（非爬虫）。优先建议安装 ArchiveBox。",
        ),
    ]
}


def get_spec(tool_name: str) -> ToolSpec | None:
    return REGISTRY.get(tool_name)


_version_cache: dict[str, str | None] = {}


async def detect_version(spec: ToolSpec) -> str | None:
    """Return version string if the tool is installed & runnable, else None."""
    if spec.name == "builtin-web-saver":
        return "1.0.0"
    if not spec.executables:
        return None
    if spec.name in _version_cache:
        return _version_cache[spec.name]
    exe = shutil.which(spec.executables[0])
    if not exe:
        for alt in spec.executables[1:]:
            exe = shutil.which(alt)
            if exe:
                break
    if not exe:
        _version_cache[spec.name] = None
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            exe, *spec.version_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=_NO_WINDOW,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            _version_cache[spec.name] = None
            return None
        text = out.decode("utf-8", errors="replace")
        m = re.search(spec.version_regex, text)
        ver = m.group(1) if m else "unknown"
        _version_cache[spec.name] = ver
        return ver
    except Exception:
        _version_cache[spec.name] = None
        return None


_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW on Windows; ignored elsewhere


def resolve_executable(spec: ToolSpec) -> str | None:
    if spec.name == "builtin-web-saver":
        return "builtin"
    for name in spec.executables:
        exe = shutil.which(name)
        if exe:
            return exe
    return None


# ---------------------------------------------------------------------------
# argv builders
# ---------------------------------------------------------------------------

def build_download_argv(spec: ToolSpec, exe: str, url: str, out_dir: str, options: dict) -> list[str]:
    """Build the command line for a download task. options keys: quality, format, extra."""
    name = spec.name
    if name == "yt-dlp":
        quality = options.get("quality", "best")
        fmt = ["-f", quality] if quality not in ("best", "") else []
        return [
            exe, *fmt, "--continue", "--newline", "--no-playlist" if options.get("no_playlist", True) else "--yes-playlist",
            "-o", f"{out_dir}/%(title)s.%(ext)s", url,
        ]
    if name == "you-get":
        return [exe, "--no-caption", "-o", out_dir, url]
    if name == "gallery-dl":
        return [exe, "-d", out_dir, "--filesize-max", "500M", url]
    if name == "lncrawl":
        # lightnovel-crawler >= 4.x: `lncrawl crawl <url> --noin --all -f txt`
        # --resume/--missing skips already-downloaded chapters (free resume).
        fmt = options.get("format", "txt")
        return [exe, "crawl", url, "--noin", "--all", "--resume", "-f", fmt]
    if name == "novel-downloader":
        return [exe, url, "--output", out_dir]
    if name == "FictionDown":
        return [exe, "download", url, "--output", out_dir]
    if name == "so-novel":
        return [exe, url, "--output", out_dir]
    if name == "abx-dl":
        return [exe, url, "--output", out_dir] if options else [exe, url, out_dir]
    if name in ("DXC", "vget", "pull-vids", "image-harvest"):
        return [exe, url, "-o", out_dir]
    if name == "archivebox":
        # archivebox add inside an initialized archive dir
        return [exe, "add", url, "--output-dir", out_dir]
    raise ValueError(f"工具 {name} 不支持下载")


def build_search_argv(spec: ToolSpec, exe: str, query: str, limit: int = 8) -> list[str] | None:
    name = spec.name
    if name == "yt-dlp":
        return [exe, "--flat-playlist", "--print", "%(title)s\t%(url)s", f"ytsearch{limit}:{query}"]
    if name == "lncrawl":
        return [exe, "search", query, "--limit", str(min(limit, 25))]
    return None


def parse_search_output(spec: ToolSpec, text: str) -> list[dict]:
    """Parse tool-specific search stdout into [{title, url}]."""
    results: list[dict] = []
    name = spec.name
    if name == "yt-dlp":
        for line in text.splitlines():
            if "\t" in line:
                title, url = line.split("\t", 1)
                if title.strip() and url.strip():
                    results.append({"title": title.strip(), "url": url.strip()})
    elif name == "lncrawl":
        # Output format:
        #   📖 Novel Title  (3 results)
        #     ➡ https://site.com/book
        #       ongoing
        current_title = ""
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("📖"):
                current_title = re.sub(r"^\S+\s*", "", s).split("(")[0].strip()
            elif s.startswith("➡"):
                url = s.lstrip("➡").strip()
                if url:
                    results.append({"title": current_title or url, "url": url})
    return results[:20]


# ---------------------------------------------------------------------------
# progress parsing
# ---------------------------------------------------------------------------

_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)%")
_SPEED = re.compile(r"at\s+([\d.]+\s*[KMGT]?i?B/s)|([\d.]+\s*[KMGT]?i?B/s)\s")
_ETA = re.compile(r"ETA[:\s]+(\d{1,2}:\d{2}(?::\d{2})?)")
_RATIO = re.compile(r"\[([#=\-.]*)\]\s*(\d+)\s*/\s*(\d+)")


def parse_progress_line(spec: ToolSpec, line: str) -> dict:
    """Extract progress info from a tool output line -> {progress, speed, eta, message}."""
    info: dict = {}
    m = _PCT.search(line)
    if m:
        try:
            info["progress"] = min(100.0, float(m.group(1)))
        except ValueError:
            pass
    ms = _SPEED.search(line)
    if ms:
        info["speed"] = (ms.group(1) or ms.group(2) or "").strip()
    me = _ETA.search(line)
    if me:
        info["eta"] = me.group(1)
    mr = _RATIO.search(line)
    if mr and int(mr.group(3)) > 0:
        done, total = int(mr.group(2)), int(mr.group(3))
        info["progress"] = min(100.0, done * 100.0 / total)
        info["message"] = f"{done}/{total}"
    # per-tool niceties
    if spec.name == "yt-dlp" and "[download] Destination:" in line:
        info["message"] = line.split("Destination:")[-1].strip()[-80:]
    if spec.name == "gallery-dl" and line.strip().startswith("./"):
        info["message"] = f"下载文件 {line.strip().split('/')[-1]}"
        info["speed"] = ""
    if spec.name == "lncrawl":
        if "Retrieving novel info" in line:
            info["message"] = "正在获取小说信息…"
        elif re.search(r"\d+\s+volumes?,\s+\d+\s+chapters?", line):
            info["message"] = line.strip()[:80]
        elif "Downloading chapters" in line or mr:
            info["message"] = info.get("message", "正在下载章节…")
    return {k: v for k, v in info.items() if v not in ("", None)}
