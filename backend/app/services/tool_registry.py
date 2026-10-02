"""Tool registry: definitions, availability detection, argv builders, progress parsers.

This is the heart of the "tool scheduling" architecture: MoRead never crawls by
itself -- it schedules professional open-source downloaders found on PATH.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass, field

from .. import config


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
            executables=["novel-cli", "novel-downloader", "novel-cli.exe", "novel-downloader.exe"],
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
            executables=["so-novel", "so-novel.exe", "sonovel", "sonovel.exe"],
            content_types=["novel"],
            install_hint="从 GitHub Releases 下载：github.com/freeok/so-novel",
            docs_url="https://github.com/freeok/so-novel",
            remark="小说专项聚合下载器，自带 JRE（tools/bin/so-novel）",
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
            install_hint="cargo build（Rust 源码）：github.com/3iqo/DXC",
            docs_url="https://github.com/3iqo/DXC",
            remark="多媒体全能下载器，自动检测并下载 URL 中的内容",
        ),
        ToolSpec(
            name="vget", display="vget", category="universal",
            executables=["vget", "vget.exe"],
            content_types=["auto", "image", "video", "audio"],
            install_hint="从 GitHub Releases 下载：github.com/guiyumin/vget",
            docs_url="https://github.com/guiyumin/vget",
            remark="多媒体全能下载器（视频/音频/播客/PDF）",
        ),
        ToolSpec(
            name="pull-vids", display="pull-vids", category="video",
            executables=["pull-vids", "pull-vids.exe"],
            content_types=["video"],
            install_hint="从 GitHub Releases 下载：github.com/vib795/pull-vids",
            docs_url="https://github.com/vib795/pull-vids",
            remark="视频批量拉取工具",
        ),
        ToolSpec(
            name="image-harvest", display="Image Harvest", category="image",
            executables=["image-harvest", "image-harvest.exe", "ih"],
            content_types=["image"],
            install_hint="pip install image-harvest",
            docs_url="https://pypi.org/project/image-harvest/",
            remark="图片批量采集工具",
        ),
        ToolSpec(
            name="archivebox", display="ArchiveBox", category="page",
            executables=["archivebox", "archivebox.exe"],
            version_args=["version"],
            version_regex=r"v(\d+\.[\w.\-+]+)",   # "ArchiveBox v0.7.1 Cpython ..."
            content_types=["page"],
            install_hint="docker run -v $PWD/data:/data archivebox/archivebox  或  pip install archivebox",
            docs_url="https://github.com/ArchiveBox/ArchiveBox",
            remark="网页完整归档：HTML / PDF / PNG 截图",
        ),
        ToolSpec(
            name="item-fetch", display="文件直链下载", category="file",
            executables=[],                     # builtin: httpx direct fetch
            content_types=["file", "auto", "image", "video", "audio"],
            install_hint="无需安装（内置）",
            remark="直接下载文件直链：压缩包/APK/图片/视频等任意文件，支持选择性下载预览项",
        ),
        ToolSpec(
            name="web2novel", display="网页转小说(OCR)", category="novel",
            executables=[],                     # builtin: trafilatura + Edge截图 + RapidOCR
            content_types=["novel"],
            install_hint="无需安装（内置兜底，OCR 依赖 Edge/Chrome）",
            remark="兜底：提取网页正文生成 TXT；图片化页面自动截图 OCR 识别文字",
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


def tool_search_path() -> str:
    """PATH plus MoRead's own tools dirs (tools/ and tools/bin).

    Single-binary downloaders fetched from GitHub Releases live there, so they
    are found without polluting the system PATH.
    """
    dirs = [str(config.TOOLS_DIR), str(config.TOOLS_DIR / "bin")]
    return os.pathsep.join(dirs + [os.environ.get("PATH", "")])


def which_tool(exe: str) -> str | None:
    """shutil.which across PATH + MoRead tools dirs. .cmd/.bat shims resolve too."""
    return shutil.which(exe, path=tool_search_path())


_version_cache: dict[str, str | None] = {}


async def detect_version(spec: ToolSpec) -> str | None:
    """Return version string if the tool is installed & runnable, else None."""
    if spec.name in ("builtin-web-saver", "web2novel", "item-fetch"):
        return "1.0.0"
    if not spec.executables:
        return None
    if spec.name in _version_cache:
        return _version_cache[spec.name]
    exe = which_tool(spec.executables[0])
    if not exe:
        for alt in spec.executables[1:]:
            exe = which_tool(alt)
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
            # 二进制存在但版本探测失败（如不支持 --version）→ 视为已安装、版本未知
            _version_cache[spec.name] = "unknown"
            return "unknown"
        text = out.decode("utf-8", errors="replace")
        m = re.search(spec.version_regex, text)
        ver = m.group(1) if m else "unknown"
        _version_cache[spec.name] = ver
        return ver
    except Exception:
        # 找得到可执行文件但无法运行 → 仍视为已安装（下载时会给出明确错误）
        _version_cache[spec.name] = "unknown"
        return "unknown"


_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW on Windows; ignored elsewhere


# Preferred fallback order per category when the picked tool fails
# (task manager retries down this list automatically).
FALLBACK_CHAINS: dict[str, list[str]] = {
    "video": ["yt-dlp", "you-get", "pull-vids", "vget", "abx-dl"],
    "image": ["gallery-dl", "image-harvest", "abx-dl"],
    "novel": ["lncrawl", "novel-downloader", "so-novel", "FictionDown", "web2novel"],
    "file": ["item-fetch"],
    "page": ["archivebox", "builtin-web-saver"],
    "universal": ["abx-dl", "DXC", "vget", "yt-dlp"],
}


def fallback_chain(spec: ToolSpec, max_alternatives: int | None = None) -> list[ToolSpec]:
    """Installed alternatives to try when `spec` fails, in preference order.
    The full ordered chain is returned by default so the builtin OCR fallback
    stays reachable."""
    chain = FALLBACK_CHAINS.get(spec.category) or FALLBACK_CHAINS["universal"]
    out: list[ToolSpec] = []
    for name in chain:
        if name == spec.name:
            continue
        alt = REGISTRY.get(name)
        if alt is not None and (resolve_executable(alt) or alt.name == "web2novel"):
            out.append(alt)
        if max_alternatives and len(out) >= max_alternatives:
            break
    return out


def ffmpeg_dir() -> str:
    """Directory containing bundled/installed ffmpeg.exe (for yt-dlp merging).

    Lookup order: packaged inside the one-file exe (bin/), tools/ffmpeg/, PATH.
    Returns a best-effort directory string; yt-dlp falls back to its own search
    when ffmpeg is not found there.
    """
    import sys
    from pathlib import Path
    candidates = []
    if getattr(sys, "frozen", False):
        # one-file 模式：datas 解压到 _MEIPASS 临时目录，bin/ 在其下
        candidates.append(Path(sys._MEIPASS) / "bin")  # noqa: SLF001
        candidates.append(Path(sys.executable).resolve().parent / "bin")
    candidates.append(Path(__file__).resolve().parents[3] / "tools" / "ffmpeg")
    for d in candidates:
        for exe_name in ("ffmpeg.exe", "ffmpeg"):
            if (d / exe_name).exists():
                return str(d)
    which = shutil.which("ffmpeg")
    return str(Path(which).parent) if which else ""


def resolve_executable(spec: ToolSpec) -> str | None:
    if spec.name in ("builtin-web-saver", "web2novel", "item-fetch"):
        return "builtin"
    for name in spec.executables:
        exe = which_tool(name)
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
        # bestvideo+bestaudio 自动合并为单个 mp4（B 站等站点默认分离流）。
        # 优先 avc1(H.264)+mp4a：浏览器 <video> 原生支持，无需转码即可播放；
        # 站点不提供 H.264 时回退任意编码（av1/vp9 等，取决于浏览器解码能力）。
        if quality in ("best", ""):
            fmt = ["-f", "bv*[vcodec^=avc1]+ba/bv*+ba/b"]
        else:
            fmt = [
                "-f",
                f"bv*[vcodec^=avc1][height<={quality}]+ba/bv*[height<={quality}]+ba/b[height<={quality}]/b",
            ]
        return [
            exe, *fmt,
            "--merge-output-format", "mp4",
            "--ffmpeg-location", ffmpeg_dir(),
            "--continue", "--newline",
            "--no-playlist" if options.get("no_playlist", True) else "--yes-playlist",
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
        # novel-cli has no --output flag; it writes relative to CWD using the
        # settings.toml the task manager seeds in the task dir.
        return [exe, "download", url, "--config", "settings.toml"]
    if name == "FictionDown":
        # 书籍 URL 是全局参数 -u（必须位于子命令之前），-o 才是输出路径
        return [exe, "-u", url, "download", "-o", out_dir]
    if name == "so-novel":
        # so-novel 的 CLI 只有 -u(书籍链接) 和 -e(格式)；输出路径来自其
        # config.ini（相对自身目录），由任务管理器在完成后收割回任务目录。
        return [exe, "-u", url, "-e", "txt"]
    if name == "abx-dl":
        # abx-dl has no output-dir flag; it writes relative to CWD, so the
        # task manager runs it inside the task's own download dir.
        return [exe, "dl", url]
    if name == "DXC":
        # DXC always writes to <HOME>/Downloads/DXC; the task manager points
        # HOME/USERPROFILE at the task's own download dir for this process.
        return [exe, "download", url]
    if name in ("vget", "image-harvest"):
        return [exe, url, "-o", out_dir]
    if name == "pull-vids":
        return [exe, "-o", out_dir, url]
    if name == "archivebox":
        # archivebox add writes into the current collection (CWD); the task
        # manager runs it inside the task dir after `archivebox init`.
        return [exe, "add", url]
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
        # 同一本书的多个镜像站点按路径 slug 去重，合并进 mirrors 列表。
        current_title = ""
        seen: dict[str, dict] = {}
        ordered: list[dict] = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("📖"):
                current_title = re.sub(r"^\S+\s*", "", s).split("(")[0].strip()
            elif s.startswith("➡"):
                url = s.lstrip("➡").strip()
                if not url:
                    continue
                slug = re.sub(r"^https?://[^/]+/", "", url).strip("/").lower()
                key = slug or url.lower()
                if key in seen:
                    seen[key].setdefault("mirrors", []).append(url)
                else:
                    item = {"title": current_title or url, "url": url, "mirrors": [url]}
                    seen[key] = item
                    ordered.append(item)
        results = ordered
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
    if spec.name == "novel-downloader":
        if "正在下载书籍" in line or "已解析 URL" in line or "使用站点" in line:
            info["message"] = line.strip()[:80]
        elif "下载完成" in line or "导出" in line:
            info["message"] = line.strip()[:80]
    if spec.name == "lncrawl":
        if "Retrieving novel info" in line:
            info["message"] = "正在获取小说信息…"
        elif re.search(r"\d+\s+volumes?,\s+\d+\s+chapters?", line):
            info["message"] = line.strip()[:80]
        elif "Downloading chapters" in line or mr:
            info["message"] = info.get("message", "正在下载章节…")
    return {k: v for k, v in info.items() if v not in ("", None)}
