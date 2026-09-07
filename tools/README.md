# tools — 外部工具封装脚本目录

墨读**不内置任何爬虫**，所有抓取能力都来自这里登记的专业开源工具。
后端通过 `asyncio.create_subprocess_exec` 非阻塞地调度它们（见
`backend/app/services/tool_registry.py` 与 `task_manager.py`）。

本目录存放：

1. `restart-backend.sh` — 本地开发用重启脚本
2. 如需为未提供 pip 包的工具（DXC / vget / pull-vids / image-harvest /
   FictionDown / So Novel）编写的包装脚本，可放在这里，并确保其可执行文件
   在 `PATH` 中（或在本目录下放同名可执行文件，并把本目录加入 PATH）。

## 已支持并推荐安装的工具

| 工具 | 用途 | 安装 |
| --- | --- | --- |
| yt-dlp | 视频/音频（1000+ 站点，支持断点续传） | `pip install yt-dlp` |
| gallery-dl | 图片（1400+ 站点） | `pip install gallery-dl` |
| you-get | 视频/音频（国内站点） | `pip install you-get` |
| lightnovel-crawler | 小说（数百站点，TXT/EPUB，断点续传） | `pip install -U lightnovel-crawler` |
| abx-dl | 多媒体全能下载（ArchiveBox 生态） | `pip install abx-dl` |
| ArchiveBox | 网页完整归档（HTML/PDF/PNG） | `docker run -v $PWD/data:/data archivebox/archivebox` |
| FictionDown | 小说专项 | [GitHub Releases](https://github.com/ma6254/FictionDown/releases) 下载二进制 |
| So Novel | 小说专项 | [GitHub Releases](https://github.com/javPower/so-novel/releases) 下载 |
| DXC / vget / pull-vids / image-harvest | 多媒体全能 | 从各自项目 Releases 下载可执行文件 |

> 未安装的工具会在「工具箱」页面明确标注状态与安装指引，应用不会因工具缺失而崩溃；
> 网页归档在没有任何外部工具时使用内置单页快照兜底（仅保存单页 HTML，非爬虫）。
