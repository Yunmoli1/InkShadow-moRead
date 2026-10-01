# tools — 外部工具目录

墨读**不内置任何爬虫**，所有抓取能力都来自专业开源工具，后端通过
`asyncio.create_subprocess_exec` 非阻塞地调度它们（见
`backend/app/services/tool_registry.py` 与 `task_manager.py`）。

后端按以下顺序查找可执行文件：`tools/` → `tools/bin/` → 系统 `PATH`。
因此从 GitHub Releases 下载的单文件工具直接放进 `tools/bin/` 即可被识别。

## 目录内容

| 路径 | 说明 |
| --- | --- |
| `restart-backend.sh` | 本地开发用重启脚本（端口 8686） |
| `ffmpeg/` | yt-dlp 合并视频流所需的 ffmpeg |
| `bin/` | 各下载器可执行文件（不入库，见 .gitignore） |
| `bin/so-novel/` | So Novel 完整程序（自带 JRE，`bin/so-novel.cmd` 为入口 shim） |
| `src/` | DXC 的 Rust 源码（cargo build 产物已复制到 bin/DXC.exe） |

## 当前已安装（2026-09-12）

| 工具 | 版本 | 安装方式 |
| --- | --- | --- |
| yt-dlp | 2026.08.19 | `pip install yt-dlp` |
| you-get | 0.4.1743 | `pip install you-get` |
| gallery-dl | 1.32.11 | `pip install gallery-dl` |
| Lightnovel Crawler | 4.14.0 | `pip install -U lightnovel-crawler` |
| Novel Downloader | — | `pip install novel-downloader` |
| abx-dl | 1.12.271 | `pip install abx-dl` |
| image-harvest | 0.1.0 | `pip install image-harvest` |
| ArchiveBox | 0.7.1 | `pip install archivebox`（Windows 需补丁，见下） |
| FictionDown | 0.1.3 | GitHub Releases → `bin/FictionDown.exe` |
| So Novel | 1.11.0 | GitHub Releases（freeok/so-novel）→ `bin/so-novel/` |
| DXC | 0.1.2 | Rust 源码 cargo build（3iqo/DXC）→ `bin/DXC.exe` |
| vget | 0.13.5 | GitHub Releases（guiyumin/vget）→ `bin/vget.exe` |
| pull-vids | 0.3.5 | GitHub Releases（vib795/pull-vids）→ `bin/pull-vids.exe` |

## Windows 平台补丁（pip 包已知问题）

abx-dl / ArchiveBox 的依赖在 Windows 上有两处 Unix-only 代码，已在本机
site-packages 打补丁（重装后需重做）：

1. `E:\Python\Lib\site-packages\pwd.py`、`fcntl.py`、`cgi.py` — 空实现/最小实现
   stub（Python 3.13+ 移除了 `cgi`，Django 3.1 需要）。
2. `archivebox/config.py` — `os.getuid()/getgid()` 与 `sqlite3.version`
   改为 `getattr` 兜底（Python 3.13+ 移除了这些 API）。

## 网络与代理

访问 GitHub 等海外资源受限时，可在「设置 → 网络」里填代理地址
（如 `http://127.0.0.1:7890`），会同时注入到所有下载工具子进程与内置
网页快照；本地 AI 服务（Ollama）不走代理。下载 GitHub Release 二进制
时可用镜像前缀：`https://ghfast.top/<原始 GitHub URL>`。
