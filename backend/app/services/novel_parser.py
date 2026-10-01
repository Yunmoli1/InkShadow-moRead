"""Novel file parsing: TXT chapter splitting & EPUB extraction (stdlib only)."""
from __future__ import annotations

import posixpath
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from sqlalchemy import delete, select

from .. import config
from ..database import SessionLocal
from ..models import Chapter, Novel

CHAPTER_PATTERNS = [
    # 第X章/节/卷/回/部/集/篇 —— 允许"第 1 章"式空格、少量装饰前缀（【【★* 等）
    re.compile(r"^[\[\s（(【★☆＊*#\-—·]{0,4}第\s*[0-9一二三四五六七八九十百千零两]+\s*[章节卷回部集篇][^\n]{0,60}$"),
    re.compile(r"^\s*Chapter\s+\d+.*$", re.IGNORECASE),
    re.compile(r"^\s*(序章|楔子|引子|前言|后记|终章|番外|序言|尾声)[^\n]{0,40}$"),
    # 纯数字行（"123"）
    re.compile(r"^\d{1,4}$"),
    # 数字编号标题（"1、标题" / "12. 标题" / "3：标题"）
    re.compile(r"^\d{1,4}\s*[、.．:：]\s*\S[^\n]{0,50}$"),
    # （一） / (十二) 式
    re.compile(r"^[（(]\s*[0-9一二三四五六七八九十百]{1,6}\s*[）)]\s*[^\n]{0,40}$"),
]
INLINE_SIZE_LIMIT = 2 * 1024 * 1024  # store content inline below 2MB total


def split_txt_into_chapters(text: str) -> list[tuple[str, str]]:
    """Split TXT text into (title, content) chapters using common CN/EN patterns."""
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue
        for pat in CHAPTER_PATTERNS:
            if pat.match(stripped):
                marks.append((i, stripped))
                break
    # de-duplicate consecutive marks & require at least 3 to trust splitting
    if len(marks) < 3:
        return [(text[:60].strip() or "全文", text)]
    chapters: list[tuple[str, str]] = []
    preface = "\n".join(lines[: marks[0][0]]).strip()
    if len(preface) > 20:  # ignore short junk lines before the first chapter
        chapters.append(("前言", preface))
    for j, (start, title) in enumerate(marks):
        end = marks[j + 1][0] if j + 1 < len(marks) else len(lines)
        body = "\n".join(lines[start + 1: end]).strip()
        chapters.append((title, body))
    return chapters


def parse_epub(path: Path) -> tuple[str, str, list[tuple[str, str]], dict[str, bytes]]:
    """Extract (title, author, chapters, images) from an EPUB file.

    Inline images become text markers ``[img:<name>]`` on their own line;
    their bytes are returned so the importer can serve them per novel."""
    with zipfile.ZipFile(path) as zf:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
        rootfile = next(c for c in container.iter() if c.tag.endswith("rootfile"))
        opf_path = rootfile.attrib["full-path"]
        opf_dir = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
        opf = ET.fromstring(zf.read(opf_path))
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        title, author = "", ""
        for md in opf.iter():
            if md.tag.endswith("metadata"):
                for el in md:
                    if el.tag.endswith("title") and not title:
                        title = (el.text or "").strip()
                    if el.tag.endswith("creator") and not author:
                        author = (el.text or "").strip()
                break
        manifest: dict[str, str] = {}
        spine: list[str] = []
        for el in opf.iter():
            if el.tag.endswith("item"):
                manifest[el.attrib["id"]] = el.attrib.get("href", "")
            elif el.tag.endswith("itemref"):
                spine.append(el.attrib["idref"])
        chapters: list[tuple[str, str]] = []
        images: dict[str, bytes] = {}
        lower_names = {n.lower(): n for n in zf.namelist()}
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            # href 在 OPF 中可能被 URL 编码（空格 → %20 等），必须解码后再查 zip
            full = unquote(f"{opf_dir}/{href}" if opf_dir else href)
            try:
                html = zf.read(full).decode("utf-8", errors="replace")
            except KeyError:
                # 兜底：按文件名（忽略目录与大小写）匹配 zip 条目
                base = full.rsplit("/", 1)[-1].lower()
                match = lower_names.get(base)
                if match is None:
                    continue
                html = zf.read(match).decode("utf-8", errors="replace")
            html = _extract_epub_images(zf, full, html, images)
            text = _html_to_text(html)
            if len(text.strip()) < 5 and not re.search(r"\[img:[\w.\-]+\]", text):
                continue  # 只跳过真正的空白页（封面/版权等），保留短章节
            t = _first_heading(html) or f"章节 {len(chapters) + 1}"
            chapters.append((t, text))
        if not chapters:
            raise ValueError("EPUB 中未找到可读章节")
        return title or path.stem, author, chapters, images


_IMG_TAG_RE = re.compile(r"<(img|image)\b[^>]*>", re.I)
_IMG_SRC_RE = re.compile(r"""(?:src|xlink:href|href)\s*=\s*["']([^"']+)["']""", re.I)


def _extract_epub_images(zf: zipfile.ZipFile, chapter_path: str, html: str, images: dict[str, bytes]) -> str:
    """Replace <img>/<image> tags with [img:<name>] markers; collect bytes.

    Zip entry paths are resolved relative to the chapter document, matching
    how EPUB OCF references work."""
    from urllib.parse import unquote

    chapter_dir = chapter_path.rsplit("/", 1)[0] if "/" in chapter_path else ""
    cache: dict[str, str | None] = {}

    def _resolve(src: str) -> str | None:
        src = unquote(src.split("#")[0].strip())
        if not src or src.startswith(("http://", "https://", "data:")):
            return None
        if src in cache:
            return cache[src]
        target = posixpath.normpath(posixpath.join(chapter_dir, src)) if chapter_dir else posixpath.normpath(src)
        name = None
        try:
            zf.getinfo(target)
            base = posixpath.basename(target)
            stem, ext = posixpath.splitext(base)
            ext = ext.lower() or ".img"
            name = f"img{len(images) + 1:03d}_{re.sub(r'[\\/:*?\"<>| ]', '_', stem)[:40]}{ext}"
            images[name] = zf.read(target)
        except KeyError:
            name = None
        cache[src] = name
        return name

    def _sub(m: re.Match) -> str:
        src_m = _IMG_SRC_RE.search(m.group(0))
        if not src_m:
            return ""
        name = _resolve(src_m.group(1))
        return f"\n\n[img:{name}]\n\n" if name else ""

    return _IMG_TAG_RE.sub(_sub, html)


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|h[1-6]|li)>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n\n".join(ln for ln in lines if ln)


def _first_heading(html: str) -> str:
    m = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S | re.I)
    if m:
        return _html_to_text(m.group(1)).strip()[:80]
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return _html_to_text(m.group(1)).strip()[:80] if m else ""


async def import_novel_file(
    path: Path, source_url: str = "", title: str = "", author: str = "",
    fallback_title: str | None = None,
) -> Novel:
    """Import a local TXT/EPUB file into the library. Returns the Novel row.

    fallback_title is used when the TXT first line is a chapter heading
    (i.e. the file itself carries no book title)."""
    suffix = path.suffix.lower()
    images: dict[str, bytes] = {}
    if suffix == ".epub":
        ftitle, fauthor, chapters, images = parse_epub(path)
        title = title or ftitle
        author = author or fauthor
    elif suffix == ".txt":
        raw = await _read_text_any_encoding(path)
        chapters = split_txt_into_chapters(raw)
        first_line = raw.splitlines()[0].strip() if raw.splitlines() else ""
        if not title:
            if first_line and len(first_line) <= 60 and not any(p.match(first_line) for p in CHAPTER_PATTERNS):
                title = first_line
            else:
                title = fallback_title or path.stem
    else:
        raise ValueError(f"不支持的文件类型: {suffix}（仅支持 TXT/EPUB）")
    if not chapters:
        raise ValueError("未解析到章节")

    src_size = path.stat().st_size
    async with SessionLocal() as db:
        exists = await db.scalar(select(Novel).where(Novel.title == title, Novel.author == author))
        if exists and exists.total_chapters == len(chapters):
            # idempotent import; older imports may predate image extraction,
            # so backfill images + marked content when they are missing.
            if suffix == ".epub" and images and not await _novel_has_images(db, exists.id):
                await _backfill_epub_images(db, exists, chapters, images)
            return exists
        if exists:
            # 同一本书重导但解析结果不同（通常是切分规则升级）→ 重建全部章节
            novel = exists
            await db.execute(delete(Chapter).where(Chapter.novel_id == novel.id))
            old_dir = config.NOVELS_DIR / novel.id
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
        else:
            novel = Novel(
                title=title or path.stem, author=author, source_url=source_url,
                file_type=suffix.lstrip("."), total_chapters=len(chapters),
                file_size=src_size,
            )
            db.add(novel)
            await db.flush()
        novel_dir = config.NOVELS_DIR / novel.id
        novel_dir.mkdir(parents=True, exist_ok=True)
        if images:
            img_dir = config.COVERS_DIR / novel.id / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            for name, data in images.items():
                (img_dir / name).write_bytes(data)
        inline = src_size <= INLINE_SIZE_LIMIT and suffix == ".txt"
        for i, (ctitle, cbody) in enumerate(chapters):
            if inline:
                cpath, ccontent = "", cbody
            else:
                cfile = novel_dir / f"{i:05d}.txt"
                cfile.write_text(f"{ctitle}\n\n{cbody}", encoding="utf-8")
                cpath, ccontent = cfile.relative_to(config.DATA_DIR).as_posix(), ""
            db.add(Chapter(
                novel_id=novel.id, idx=i, title=ctitle,
                content_path=cpath, content=ccontent,
                word_count=len(cbody),
            ))
        novel.total_chapters = len(chapters)
        novel.file_size = src_size
        novel.file_type = suffix.lstrip(".")
        await db.commit()
        await db.refresh(novel)
        return novel


async def _novel_has_images(db, novel_id: str) -> bool:
    """True if any chapter of the novel already carries [img:] markers."""
    row = await db.scalar(
        select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.content.like("%[img:%"))
    )
    if row is not None:
        return True
    for (cpath,) in (await db.execute(
        select(Chapter.content_path).where(Chapter.novel_id == novel_id, Chapter.content_path != "")
    )).all():
        try:
            if "[img:" in (config.DATA_DIR / cpath).read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


async def _backfill_epub_images(db, novel: Novel, chapters: list[tuple[str, str]], images: dict[str, bytes]) -> None:
    """Refresh an older EPUB import with extracted images and [img:] markers."""
    img_dir = config.COVERS_DIR / novel.id / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    for name, data in images.items():
        (img_dir / name).write_bytes(data)
    rows = (await db.execute(
        select(Chapter).where(Chapter.novel_id == novel.id).order_by(Chapter.idx)
    )).scalars().all()
    for i, row in enumerate(rows):
        if i >= len(chapters):
            break
        _, body = chapters[i]
        if row.content_path:
            p = config.DATA_DIR / row.content_path
            if p.exists():
                p.write_text(f"{row.title}\n\n{body}", encoding="utf-8")
        else:
            row.content = body
        row.word_count = len(body)
    await db.commit()


async def _read_text_any_encoding(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "gb18030", "big5", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def find_local_novel_files(directory: Path) -> list[Path]:
    """Discover TXT/EPUB files in a directory (recursive)."""
    return [p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in (".txt", ".epub")]


async def import_lncrawl_output(out_dir: Path, source_url: str = "") -> Novel | None:
    """Import a lncrawl 4.x output dir (meta.txt + numbered chapter txts + cover.jpg)."""
    meta_file = None
    for cand in out_dir.rglob("meta.txt"):
        meta_file = cand
        break
    if meta_file is None:
        return None

    meta = _parse_lncrawl_meta(meta_file.read_text(encoding="utf-8", errors="replace"))
    title = meta.get("title") or out_dir.name
    author = meta.get("author") or ""
    description = meta.get("description") or ""

    # numbered chapter files, possibly under volume subdirs
    chapter_files: list[Path] = [
        p for p in out_dir.rglob("*.txt")
        if p.is_file() and p.name != "meta.txt" and p.stem.isdigit()
    ]
    if not chapter_files:
        return None
    chapter_files.sort(key=lambda p: (int(p.stem),))

    async with SessionLocal() as db:
        exists = await db.scalar(select(Novel).where(Novel.title == title, Novel.author == author))
        if exists:
            # idempotent re-import: still backfill missing cover
            cover_src = meta_file.parent / "cover.jpg"
            if exists.cover_path == "" and cover_src.exists():
                cover_dir = config.COVERS_DIR / exists.id
                cover_dir.mkdir(parents=True, exist_ok=True)
                dest = cover_dir / "cover.jpg"
                dest.write_bytes(cover_src.read_bytes())
                exists.cover_path = dest.relative_to(config.DATA_DIR).as_posix()
                await db.commit()
            return exists
        novel = Novel(
            title=title, author=author, source_url=source_url or meta.get("url", ""),
            description=description, file_type="txt", category="小说",
            total_chapters=len(chapter_files),
        )
        db.add(novel)
        await db.flush()
        # cover
        cover_src = meta_file.parent / "cover.jpg"
        if cover_src.exists():
            cover_dir = config.COVERS_DIR / novel.id
            cover_dir.mkdir(parents=True, exist_ok=True)
            dest = cover_dir / "cover.jpg"
            dest.write_bytes(cover_src.read_bytes())
            novel.cover_path = dest.relative_to(config.DATA_DIR).as_posix()
        novel_dir = config.NOVELS_DIR / novel.id
        novel_dir.mkdir(parents=True, exist_ok=True)
        total_size = 0
        for i, cf in enumerate(chapter_files):
            raw = await _read_text_any_encoding(cf)
            lines = raw.splitlines()
            ctitle = lines[0].strip()[:100] if lines else f"第{i + 1}章"
            cbody = "\n".join(lines[1:]).strip() or raw
            cfile = novel_dir / f"{i:05d}.txt"
            cfile.write_text(f"{ctitle}\n\n{cbody}", encoding="utf-8")
            total_size += cfile.stat().st_size
            db.add(Chapter(
                novel_id=novel.id, idx=i, title=ctitle,
                content_path=cfile.relative_to(config.DATA_DIR).as_posix(),
                content="", word_count=len(cbody),
            ))
        novel.file_size = total_size
        await db.commit()
        await db.refresh(novel)
        return novel


def _parse_lncrawl_meta(text: str) -> dict:
    """Parse lncrawl meta.txt: url / title / author / description blocks."""
    out: dict[str, str] = {}
    blocks = [b.strip() for b in text.split("-" * 40)]
    if blocks and blocks[0].startswith("http"):
        out["url"] = blocks[0].splitlines()[0].strip()
    for block in blocks[1:]:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if "title" not in out:
            out["title"] = lines[0].strip()
            if len(lines) > 1 and lines[1].lower().startswith("by"):
                out["author"] = lines[1][2:].strip().lstrip(",").strip()
        elif "description" not in out and not lines[0].lower().startswith(("tags:", "volumes:", "chapters:")):
            out["description"] = " ".join(lines)
        for ln in lines:
            low = ln.lower()
            if low.startswith("author:"):
                out["author"] = ln.split(":", 1)[1].strip()
            elif low.startswith("title:"):
                out["title"] = ln.split(":", 1)[1].strip()
    return out
