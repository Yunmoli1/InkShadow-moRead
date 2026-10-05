# 墨读 MoRead

**个人本地知识库** — 通过调度专业开源工具，实现对**小说、图片、音频、视频及完整网页**的获取、管理与预览。
仅供个人学习研究，所有数据仅保存在本机，绝不联网上传。

![stack](https://img.shields.io/badge/FastAPI-SQLAlchemy%202.0%20async-009688) ![fe](https://img.shields.io/badge/React%2018-Vite%20·%20Tailwind%20v4%20·%20shadcn%2Fui-61dafb) ![pwa](https://img.shields.io/badge/PWA-offline--ready-5a0fc8)

## ✨ 核心特性

- **工具调度架构**：应用不内置爬虫。后端统一适配器通过 `asyncio.create_subprocess_exec`
  非阻塞调度 `yt-dlp` / `gallery-dl` / `you-get` / `lncrawl` / `ArchiveBox` 等专业工具，
  实时解析进度并通过 SSE 推送；工具未安装时返回明确状态，应用不崩溃。
- **万能抓取**：输入任意 URL，选择内容类型（自动识别/图片/视频/音频/网页/小说），一键抓取。
- **任务中心**：排队/进行/暂停/完成/失败全生命周期管理，**支持暂停恢复与断点续传**，
  SSE 实时进度推送，断线指数退避自动重连；失败自动分类（工具未安装/网络/需要登录/超时等）
  并给出建议动作，2 小时总超时防挂死；任务详情可看完整日志、回退链与「相同工具重试」。
- **追更与换源**：书架订阅追更（每 6 小时自动检查新章）；一键换源调度多小说工具重抓。
- **OPDS 书库目录**：KOReader 等阅读器可直接浏览书架，在线下载 TXT 与**按需生成的 EPUB**。
- **标签筛选**：AI 自动标签落库后，书架/资源库可按标签 chips 一键过滤。
- **可观测性**：结构化 JSON 日志（脱敏、5MB×5 轮转）、`/api/metrics` 运行指标
  （30 天成功率/平均耗时/回退次数）、liveness 与 readiness 分离的健康检查、
  SQLite 每日例行维护（WAL checkpoint + VACUUM）。
- **资源库**：图片/视频/音频/网页归档统一展示、搜索、筛选；内置播放器与图片画廊。
- **沉浸阅读器**：滚动/分页双模式（framer-motion 翻页动画）、字体与纸张主题调节、
  **react-window 虚拟滚动章节目录（1000+ 章节流畅）**、AI 摘要侧边栏、TTS 语音朗读（Web Speech API）。
- **读书笔记**：划选添加、按章节筛选、导出 Markdown、Ctrl+Z 撤销删除、Ctrl+S 快速保存。
- **阅读统计**：阅读时长（30 秒心跳采集）、已读章节、年度报告。
- **本地备份**：书架/章节/笔记/设置导出为 **AES-GCM 加密 JSON**（WebCrypto，密码不出本机）。
- **PWA**：可安装到桌面/手机，离线访问已缓存内容。
- **大文件不卡 UI**：TXT 导入使用 Web Worker 后台解析（>10MB 文件亦不阻塞界面）。

## 🚀 快速开始

### 方式零：单文件可执行程序（零依赖）

```bash
# 构建（需 Python 3.11+ 与 Node 构建环境各一，仅构建者需要）
cd frontend && pnpm install && pnpm run build && cd ..
pip install pyinstaller
pyinstaller moread.spec --noconfirm
cp dist/moread.exe releases/        # Windows；macOS/Linux 在对应平台执行同样命令
```

双击 `moread.exe` 即可运行：自动打开浏览器访问 <http://127.0.0.1:8686>。
前后端与页面资源全部内嵌于单一二进制，**运行机器无需安装 Python / Node / Docker**；
所有用户数据（数据库、下载、备份）写在 exe 同级的 `data/` 目录，随目录整体迁移。
设置环境变量 `MOREAD_DATA_DIR` 可自定义数据目录，`MOREAD_HOST` / `MOREAD_PORT` 可改监听地址端口，`MOREAD_NO_BROWSER=1` 禁止自动开浏览器。

**预构建产物**（`releases/`）：

| 文件 | 平台 | 基线 |
| --- | --- | --- |
| `moread.exe` | Windows x64 | 任意 Win10/11，双击即用 |
| `moread-linux` | Linux x86_64 | glibc ≥ 2.31（Debian 11+ / Ubuntu 20.04+），`chmod +x moread-linux && ./moread-linux` |
| `moread.apk` | Android 7.0+（arm64/arm/x86 通用） | WebView 壳客户端，见下 |

Linux 版由 Docker 容器（`python:3.12-bullseye`）内执行同一 `moread.spec` 构建，
并已在未安装 Python 的纯净 Debian 容器中完成功能验证。

### Android APK

`android-apk/` 内是手工构建的 WebView 壳客户端（无 Gradle，`bash android-apk/build-apk.sh` 可复现构建）：
前端全部内嵌进 APK；`/api` 请求经应用内置反向代理转发到 PC 端墨读服务器。

使用方式：
1. 电脑上运行 `moread.exe`（或 Linux 版），首次启动后按提示修改配置使局域网可访问：
   设置 `MOREAD_HOST=0.0.0.0` 环境变量重启程序（Windows 侧需在防火墙放行 8686 端口）。
2. 手机安装 `moread.apk`，启动后按提示填入电脑局域网地址（如 `192.168.1.100:8686`，右下角 ⚙ 可随时修改）。
3. 书架/阅读/笔记/下载/媒体播放等全部功能均通过电脑端服务执行，手机端完整可用。

> 说明：PyInstaller 不支持交叉编译，macOS 版需在 Mac 上执行同一 spec 构建。

### 方式一：Docker 一键启动（推荐）

```bash
docker compose up -d --build
# 打开 http://127.0.0.1:8686
```

镜像内置 `yt-dlp` / `gallery-dl` / `you-get` / `lncrawl`，开箱即用。
可选启用 ArchiveBox 归档服务：`docker compose --profile archive up -d`。

### 方式二：本地开发

```bash
# 1) 后端（Python 3.11+）
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8686

# 2) 前端（Node 20+，pnpm）
cd frontend
pnpm install
pnpm run dev          # 开发模式 http://localhost:5173（已代理 /api）
pnpm run build        # 产物输出 frontend/dist，由后端静态托管

# 3) 安装外部工具（至少装一个即可开始抓取）
pip install yt-dlp gallery-dl you-get lightnovel-crawler
```

访问入口：

| 地址 | 说明 |
| --- | --- |
| `http://127.0.0.1:8686` | 应用（前端 + API 一体） |
| `http://127.0.0.1:8686/docs` | OpenAPI 交互文档（全部 API 可在页面直接调试） |

## 📦 外部工具安装指引

| 工具 | 用途 | 安装 |
| --- | --- | --- |
| yt-dlp | 视频/音频专项（1000+ 网站，断点续传） | `pip install yt-dlp` |
| gallery-dl | 图片专项（1400+ 网站） | `pip install gallery-dl` |
| you-get | 视频/音频专项 | `pip install you-get` |
| lncrawl | 小说专项（数百站点，输出 TXT/EPUB） | `pip install -U lightnovel-crawler` |
| abx-dl | 多媒体全能下载 | `pip install abx-dl` |
| ArchiveBox | 网页完整归档（HTML/PDF/PNG） | `docker run -v $PWD/data:/data archivebox/archivebox` |
| FictionDown | 小说专项 | 从 [GitHub Releases](https://github.com/ma6254/FictionDown/releases) 下载 |
| So Novel | 小说专项 | 从 [GitHub Releases](https://github.com/javPower/so-novel/releases) 下载 |
| DXC / vget / pull-vids / image-harvest | 多媒体全能 | 从各自项目 Releases 下载可执行文件并加入 PATH |

> 工具箱页面会实时检测每个工具的安装状态与版本，未安装时给出明确安装指引。
> 在没有任何归档工具时，网页抓取使用「内置单页快照」兜底（仅保存单页 HTML）。

## 🗂 项目结构

```
├── backend/            # FastAPI + SQLAlchemy 2.0 (async) + SQLite (aiosqlite)
│   ├── app/
│   │   ├── main.py             # 入口：API + 前端静态托管 + SPA 回退
│   │   ├── models.py           # Novel/Chapter/Note/Media/Task/Session/Setting
│   │   ├── routers/            # tools / tasks(SSE) / novels / media / settings
│   │   ├── tests/              # pytest API 测试
│   │   └── services/
│   │           ├── tool_registry.py    # 工具注册表：检测/版本/argv/进度解析/搜索
│   │           ├── task_manager.py     # 子进程生命周期 + SSE 事件总线 + 断点续传
│   │           ├── novel_parser.py     # TXT 章节切分 / EPUB / 工具产物导入
│   │           ├── web_saver.py        # 内置单页快照（兜底）
│   │           ├── ai_service.py       # Ollama 默认 / OpenAI 兼容
│   │           └── storage.py          # 配额与清理
│   └── data/                   # 运行数据（数据库/小说/媒体/备份，已 gitignore）
├── frontend/           # React 18 + Vite + TS + Zustand + Tailwind v4 + shadcn/ui + PWA
│   └── src/
│       ├── pages/              # 万能抓取/任务中心/资源库/书架/阅读器/统计/工具箱/设置
│       ├── components/         # AppShell / CommandPalette(Ctrl+K) / Toast / ui/*
│       ├── workers/            # TXT 大文件解析 Web Worker
│       └── lib/api.ts          # API 客户端 + SSE 指数退避重连
├── tools/              # 外部工具封装脚本与说明
├── .docs/design-spec.md        # 设计规范（唯一视觉标准）
└── docker-compose.yml  # 一键部署（含可选 ArchiveBox profile）
```

## ⌨️ 快捷键 / 手势

| 输入 | 功能 |
| --- | --- |
| `Ctrl+K` | 全局搜索（命令面板） |
| `Space` / `←` `→` | 阅读器分页模式翻页 |
| `Ctrl+S` | 保存当前笔记 |
| `Ctrl+Z` | 撤销上次笔记删除 |
| `T` | 切换章节目录 |
| 移动端 | 阅读器左右滑动翻页；触控区域 ≥ 44px |

## 🔒 隐私与安全

- 所有数据（数据库、下载内容、笔记、备份）仅存于本机 `backend/data/`（该目录不入版本库）。
- AI 摘要默认连接本地 Ollama（`http://localhost:11434`，模型 `llama3`）；
  可在设置中切换为 OpenAI 兼容外部 API（Key 仅存本地数据库）。
- 备份文件在前端使用 WebCrypto AES-GCM + PBKDF2(150k) 加密，密码不落盘。
- 仓库中不含任何个人数据、下载记录与运行日志。

## 🧪 质量保障

- pytest 覆盖全部 API（导入/抓取/任务生命周期/SSE/备份/健康检查/错误分类/EPUB/FTS/指标）。
- **FTS5 全文索引**：书内与全局搜索走 trigram 索引（万章级书 <150ms，含冷建索引），
  短查询与不支持 FTS 的环境自动回退 LIKE。
- **前端类型零漂移**：`pnpm gen:api` 从后端 OpenAPI 生成 `src/lib/api-types.ts`。
- Playwright 冒烟链路（书架→阅读器 / 抓取→任务→资源库）纳入 GitHub Actions CI
  （`.github/workflows/ci.yml`：pytest → 构建 → e2e 三段流水线）。
- `pnpm run build` 与 `docker compose up` 可一键构建部署。

## 📄 许可

仅供个人学习研究使用。
