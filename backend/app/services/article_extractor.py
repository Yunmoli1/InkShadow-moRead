"""网页正文提取（Wallabag 模式）：从杂乱 HTML 中抽出干净文章。

优先使用 readability-lxml；失败时退化为 <article>/<main> 启发式。
提取结果作为单章"文章"进入书架，复用阅读器全部能力（TTS/AI 摘要/笔记/搜索）。
"""
from __future__ import annotations

import re

MIN_ARTICLE_CHARS = 400  # 少于此长度视为提取失败（导航页/登录页等）


def _clean_text(html: str) -> str:
    html = re.sub(r"<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|h[1-6]|li|section|article|blockquote)>", "\n\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&ldquo;", "“"), ("&rdquo;", "”")):
        text = text.replace(a, b)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n\n".join(ln for ln in lines if ln)


def _title_of(html: str) -> str:
    m = re.search(r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']", html, re.I)
    if m:
        return m.group(1).strip()[:120]
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        return _clean_text(m.group(1)).strip()[:120]
    return ""


def extract_article(html: str) -> dict | None:
    """返回 {title, text}；正文过短（导航页/登录墙）时返回 None。"""
    if not html or len(html) < 200:
        return None
    title = _title_of(html)
    text = ""

    try:
        from readability import Document

        doc = Document(html)
        summary_html = doc.summary(html_partial=True)
        text = _clean_text(summary_html)
        if not title:
            title = (doc.short_title() or "").strip()[:120]
    except Exception:
        text = ""

    if len(text) < MIN_ARTICLE_CHARS:
        # 启发式回退：<article> / <main> / 最长文本块
        for pat in (r"<article[^>]*>(.*?)</article>", r"<main[^>]*>(.*?)</main>"):
            m = re.search(pat, html, re.S | re.I)
            if m:
                cand = _clean_text(m.group(1))
                if len(cand) > len(text):
                    text = cand
    if len(text) < MIN_ARTICLE_CHARS:
        return None
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"title": title or "未命名文章", "text": text}
