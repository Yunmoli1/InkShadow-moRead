"""B2 EPUB 按需生成：API 下载 + epub 包结构 + 缓存复用 + OPDS 链接。"""
import io
import zipfile

from app.database import SessionLocal
from app.models import Chapter, Novel


def _seed_novel() -> str:
    import asyncio
    import uuid

    nid = uuid.uuid4().hex

    async def go():
        async with SessionLocal() as db:
            db.add(Novel(id=nid, title="EPUB测试书", author="测试作者",
                         total_chapters=2))
            db.add(Chapter(novel_id=nid, idx=0, title="第一章 起点",
                           content="这是第一章的正文。\n第二段内容。"))
            db.add(Chapter(novel_id=nid, idx=1, title="第二章 终点",
                           content="这是第二章的正文。"))
            await db.commit()
    asyncio.run(go())
    return nid


def test_download_epub_roundtrip(client):
    nid = _seed_novel()
    r = client.get(f"/api/novels/{nid}/download.epub")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/epub+zip")
    raw = r.content
    # epub = zip：校验容器结构
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        assert "mimetype" in names and "META-INF/container.xml" in names
        assert z.read("mimetype") == b"application/epub+zip"
        opf = [n for n in names if n.endswith(".opf")]
        assert opf, "缺少 OPF 包描述文件"
        opf_text = z.read(opf[0]).decode("utf-8")
        assert "EPUB测试书" in opf_text
        import os

        xhtmls = [n for n in names
                  if os.path.basename(n).startswith("chap_") and n.endswith(".xhtml")]
        assert len(xhtmls) == 2, f"应有 2 个章节文件，实际 {len(xhtmls)}: {names}"
        chap1 = z.read(xhtmls[0]).decode("utf-8")
        assert "第一章 起点" in chap1 and "第二段内容" in chap1

    # 缓存复用：第二次请求命中同一缓存文件
    r2 = client.get(f"/api/novels/{nid}/download.epub")
    assert r2.status_code == 200 and len(r2.content) == len(raw)


def test_download_epub_missing_novel(client):
    r = client.get("/api/novels/nonexistent/download.epub")
    assert r.status_code == 404


def test_opds_feed_has_epub_link(client):
    nid = _seed_novel()
    xml = client.get("/opds/books").text
    assert f"/api/novels/{nid}/download.epub" in xml
    assert "application/epub+zip" in xml
