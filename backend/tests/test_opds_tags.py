"""OPDS 与 AI 标签回归：feed 结构、Basic 认证、整书下载、打标补建。"""
import base64
import uuid
import xml.etree.ElementTree as ET

from tests.test_api import _make_novel_txt


def test_opds_feeds_and_download(client):
    """回归（第四步）：OPDS 根/书目 feed 与整书 TXT 下载。"""
    r = client.post("/api/novels/import", files=[
        ("files", (f"opds_{uuid.uuid4().hex[:6]}.txt", _make_novel_txt(3), "text/plain")),
    ])
    assert r.status_code == 200

    root_xml = client.get("/opds")
    assert root_xml.status_code == 200
    assert "opds-catalog" in root_xml.headers["content-type"]
    tree = ET.fromstring(root_xml.text)
    assert tree.tag.endswith("feed")
    assert any(e.find("{*}title").text == "全部书籍" for e in tree.findall("{*}entry"))

    books = client.get("/opds/books")
    assert books.status_code == 200
    btree = ET.fromstring(books.text)
    entries = btree.findall("{*}entry")
    assert len(entries) >= 1
    link = entries[0].find('{*}link[@rel="http://opds-spec.org/acquisition"]')
    assert link is not None and link.get("href").startswith("/api/novels/")

    href = link.get("href")
    dl = client.get(href)
    assert dl.status_code == 200 and "测试之书" in dl.text and "第1章" in dl.text

    nid = href.split("/api/novels/")[1].split("/")[0]
    client.delete(f"/api/novels/{nid}")


def test_opds_token_via_basic_auth(client):
    """回归：启用令牌后 OPDS 走 Basic 认证（密码=令牌），/api 走 Basic 也可通过。"""
    basic = base64.b64encode(b"reader:opds-token").decode()
    try:
        client.put("/api/settings", json={"access_token": "opds-token"})
        assert client.get("/opds").status_code == 401
        assert client.get("/opds", headers={"Authorization": f"Basic {basic}"}).status_code == 200
        assert client.get("/api/novels", headers={"Authorization": f"Basic {basic}"}).status_code == 200
        assert client.get("/opds/books?token=opds-token").status_code == 200
    finally:
        client.put("/api/settings", json={"access_token": ""},
                   headers={"Authorization": f"Basic {basic}"})


def test_auto_tag_backfill_endpoint(client):
    """回归（第五步）：补建端点在 AI 不可用时静默返回 0，不崩溃。"""
    r = client.post("/api/media/auto-tag")
    assert r.status_code == 200 and r.json()["tagged"] == 0
    r2 = client.post("/api/novels/auto-tag")
    assert r2.status_code == 200 and "tagged" in r2.json()
