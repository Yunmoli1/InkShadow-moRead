# 墨读 MoRead 项目功能与优化建议

> 生成日期：2026-10-04  
> 阅读范围：`README.md`、`backend/app`、`backend/tests`、`frontend/src`、部署与打包配置  
> 目标：整理当前能力，标出高价值的稳定性、性能、安全和体验改进项。

## 1. 项目定位

墨读是一个本地优先的个人知识库。它把小说、图片、音频、视频和网页归档统一到一个界面中，后端不自行实现各站点爬虫，而是通过工具注册表调度 `yt-dlp`、`gallery-dl`、`lncrawl`、ArchiveBox 等外部工具，并把产物导入本地书库或媒体库。

核心边界如下：

- 数据和备份默认落在本机 `backend/data`（可由 `MOREAD_DATA_DIR` 覆盖）。
- 前端是 React 18 + Vite + TypeScript + Zustand + Tailwind/shadcn 风格 UI。
- 后端是 FastAPI + SQLAlchemy 2.0 async + SQLite/aiosqlite。
- 下载任务由单进程 `TaskManager` 管理，进度通过 SSE 推送。
- AI 摘要默认连接本机 Ollama，也支持 OpenAI 兼容接口；TTS 使用浏览器 Web Speech API。

## 2. 功能地图

| 功能域 | 当前能力 | 主要入口 |
| --- | --- | --- |
| 万能抓取 | URL 自动识别；按小说/图片/视频/音频/网页/文件选择类型；预览可下载条目；选择性下载 | `frontend/src/pages/Grab.tsx`、`backend/app/routers/tools.py` |
| 外部工具调度 | 检测安装状态和版本；按类别选工具；失败后按回退链切换；解析 stdout 进度 | `backend/app/services/tool_registry.py`、`task_manager.py` |
| 任务中心 | 排队、运行、暂停、恢复、取消、失败/完成；SSE 实时进度和断线重连 | `frontend/src/pages/Tasks.tsx`、`backend/app/routers/tasks.py` |
| 资源库 | 图片/视频/音频/网页/PDF/文件导入、筛选、搜索、预览、删除；视频/音频 Range 播放；缩略图和播放进度 | `frontend/src/pages/Library.tsx`、`backend/app/routers/media.py` |
| 书架与导入 | TXT/EPUB 批量导入；分类、搜索、封面；删除 | `frontend/src/pages/Shelf.tsx`、`backend/app/routers/novels.py` |
| 沉浸阅读 | 滚动/分页；章节目录；章节懒加载；书内搜索；字体、行距、纸张主题；阅读进度和 30 秒心跳 | `frontend/src/pages/Reader.tsx` |
| 笔记 | 划选摘录、章节筛选、保存/删除、撤销删除、Markdown 导出、快捷键 | `frontend/src/pages/Reader.tsx`、`backend/app/routers/novels.py` |
| AI 与语音 | 章节摘要普通/流式接口；缓存摘要；浏览器 TTS | `backend/app/services/ai_service.py`、`Reader.tsx` |
| 统计 | 总阅读时长、年度时长、已读章节、近 30 天趋势、常读小说、笔记数 | `frontend/src/pages/Stats.tsx`、`/api/novels/stats` |
| 设置与存储 | 主题、阅读器、AI、代理、配额、访问令牌；存储统计和过期下载清理 | `frontend/src/pages/Settings.tsx`、`backend/app/routers/settings.py` |
| 备份恢复 | 前端 AES-GCM + PBKDF2 加密 JSON；正文、封面、EPUB 图片、笔记、设置可导出/导入 | `/api/backup/export`、`/api/backup/import` |
| 部署形态 | 本地开发、Docker、PyInstaller 单文件、Android WebView 壳、PWA | `Dockerfile`、`docker-compose.yml`、`android-apk/` |

## 3. 典型用户流程

### 3.1 抓取媒体或网页

1. 用户在“万能抓取”输入 URL，选择内容类型或保持自动。
2. `/api/tools/preview` 根据 URL 后缀和已安装工具给出预览。
3. `/api/tools/auto/download` 或具体工具下载接口创建 `DownloadTask`。
4. `TaskManager` 获取并发信号量，启动外部进程或内置兜底实现。
5. stdout/stderr 被解析为进度事件，写回任务并通过 `/api/tasks/{id}/status` SSE 推送。
6. 下载结束后扫描任务目录，把小说导入 `Novel/Chapter`，或把媒体写入 `MediaItem`。

### 3.2 阅读与记录

1. 书架打开 `/reader/:novelId`，先取小说信息和章节目录。
2. 阅读器按章节请求正文，章节切换时加载笔记并恢复进度。
3. 每 30 秒记录一次阅读时长；离开或切章时写入章节索引和滚动比例。
4. 笔记、AI 摘要、书内搜索分别调用独立接口。

### 3.3 备份恢复

1. 后端导出完整 JSON 到 `backend/data/backups`。
2. 前端用用户密码派生 AES-GCM 密钥并下载加密文件。
3. 导入时前端解密，再把 JSON 交给后端重建小说、章节、封面和设置。

## 4. 架构与数据模型摘要

### 后端层次

- `routers/`：HTTP 参数校验、鉴权入口、响应模型。
- `services/tool_registry.py`：工具能力、可执行文件发现、命令构造、输出解析、回退链。
- `services/task_manager.py`：子进程生命周期、暂停/恢复/取消、SSE 事件总线、下载后处理。
- `services/novel_parser.py`：TXT/EPUB/工具产物解析及章节落盘。
- `services/storage.py` / `media_assets.py`：配额、清理、缩略图和媒体元数据。
- `models.py`：`Novel`、`Chapter`、`Note`、`MediaItem`、`DownloadTask`、`ReadingSession`、`Setting`、`AiSummary`。

### 前端层次

- `App.tsx` 定义路由，`AppShell.tsx` 提供导航、主题、全局搜索、令牌输入和 SSE 状态。
- `lib/api.ts` 统一 fetch、令牌、错误转换和 SSE 自动重连。
- 页面组件按业务域拆分，阅读器承担最多交互状态。
- TXT 大文件在 `workers/txtParser.worker.ts` 中后台解析，减少主线程阻塞。

## 5. 做得比较好的地方

1. 外部工具通过注册表抽象，新增工具主要是增加 `ToolSpec` 和命令/进度解析，不必侵入页面层。
2. 任务有明确的终态，并使用 SSE 快照、增量事件和 keepalive，前端还有指数退避重连。
3. 下载失败有按内容类别的回退链，内置单页快照和网页转小说/OCR 兜底，提高了“开箱可用”程度。
4. 大书章节支持落盘，阅读器目录按批次加载，TXT 导入放到 Web Worker，考虑了大文件场景。
5. 媒体文件支持 HTTP Range，视频/音频可以拖动播放；备份回归测试覆盖了超过 2MB 的正文。
6. API 测试已经覆盖健康检查、导入、任务生命周期、备份、书内搜索、播放进度和访问令牌等核心路径。

## 6. 优化建议（按优先级）

### P0：优先修复数据正确性和任务可靠性

#### 6.1 修复备份恢复后的笔记关联

当前导出笔记保存原始 `novel_id`，但导入小说时会生成新的 UUID。导入笔记时又直接用旧 ID 查找小说，查不到就跳过（`backend/app/routers/settings.py:223-228`）。因此跨实例恢复时，小说可能恢复成功而笔记数量为 0。

建议：

- 导出时给每本书写入稳定的备份内部 ID，笔记引用该内部 ID。
- 导入小说时建立 `backup_novel_id -> new_novel_id` 映射，再用映射恢复笔记。
- 对已存在（标题+作者重复）的书也记录映射，避免其笔记被误跳过。
- 增加“书籍 + 笔记完整 round-trip”回归测试，断言笔记正文、章节号和摘录都恢复。

#### 6.2 持久化任务选项，并增加重启接管

`TaskManager.create_task` 接收 `options`，但 `DownloadTask` 没有保存该字段；恢复时 `resume()` 固定使用空字典（`backend/app/services/task_manager.py:148-161`）。选择性下载的 URL 列表、格式选择等参数因此可能在暂停后丢失。与此同时，运行中的 worker、进程和信号量都只存在内存中（`task_manager.py:105-111`），服务重启后数据库中的 `queued/running` 任务不会自动执行。

建议：

- 在 `DownloadTask` 增加 `options` JSON、`attempt`、`worker_id` 和 `last_heartbeat_at`。
- `resume()` 从数据库读取原始 options；创建任务时也保存命令快照和工具版本。
- 应用启动时扫描 `queued/running`：将无心跳的运行中任务标记为中断，按策略自动重排或明确失败。
- 用数据库锁/租约保证多 worker 部署下同一任务只有一个执行者。
- 为暂停竞态增加保护：任务刚入队时被暂停，应在启动外部进程前再次检查状态。

#### 6.3 收紧局域网访问边界

当前 CORS 允许所有来源（`backend/app/main.py:32-38`），访问令牌还允许通过查询参数传递（`main.py:53-65`），这是 SSE 和媒体标签易用，但令牌可能进入浏览器历史、代理日志或 Referer。应用默认开放且支持绑定局域网地址，安全边界需要更明确。

建议：

- 默认只允许 `127.0.0.1`/`localhost` 前端来源；开发端口通过配置显式加入 allowlist。
- API 请求优先只接受 `X-MoRead-Token`；SSE/媒体改用短时签名 URL 或一次性票据，减少长期令牌出现在 URL 中。
- 访问令牌使用常量时间比较，并限制失败重试频率。
- 在设置页明确显示“开放本机/局域网”和令牌状态；启动日志打印实际监听地址与风险提示。

### P1：改善大文件性能、可扩展性和可诊断性

#### 6.4 将同步磁盘 I/O 移出异步请求路径

批量媒体导入和小说导入在 async 路由中使用同步 `open/write`（`backend/app/routers/media.py:63-86`、`novels.py:92-113`）；备份导出也会在请求协程中 `read_bytes/write_text`。大文件上传或导出期间会阻塞事件循环，影响 SSE 和其他请求。

建议使用分块异步写入，或把文件操作放入 `asyncio.to_thread`；导出采用临时文件 + 原子替换，避免中途失败留下损坏备份。同步增加单文件大小、批量总大小和剩余配额校验。

#### 6.5 优化列表接口和全文搜索

媒体和小说列表接口只返回数组，不返回 `total`；前端虽然传递 `page/page_size`，但书架和资源库缺少可靠的分页导航。阅读器初次最多请求 500 个章节（`frontend/src/pages/Reader.tsx:87-94`），大书仍会产生较大的首屏响应。

建议：

- 统一返回 `{items,total,page,page_size}`，前端实现真正的分页或无限滚动。
- 章节目录改为按需窗口加载，首屏只取当前章节附近数据。
- 为 `MediaItem.title/source_url`、`Note(novel_id,chapter_idx)` 增加索引；章节正文搜索量上升后引入 SQLite FTS5，并保留当前接口格式。
- 全局搜索增加类型、时间和分页参数，避免固定 `limit(10)` 导致结果不可发现。

#### 6.6 建立任务可观测性和错误分类

当前许多路径用宽泛的 `except Exception`，例如媒体资源补建和备份图片恢复会静默忽略错误；任务日志只保留尾部 200 行。用户能看到“失败”，但不一定知道是工具未安装、网络失败、权限失败、产物为空还是导入失败。

建议：

- 统一错误码：`TOOL_NOT_FOUND`、`NETWORK_ERROR`、`AUTH_REQUIRED`、`NO_CONTENT`、`IMPORT_ERROR`、`QUOTA_EXCEEDED` 等。
- 任务记录 `phase`、`last_error_code`、`retry_count` 和耗时；日志同时写结构化 JSON 文件并做大小轮转。
- 增加 `/api/metrics` 或最小化统计：任务成功率、平均耗时、回退次数、SSE 订阅数、存储占用。
- 对外部工具命令、URL 和令牌做脱敏后再写日志。

#### 6.7 补齐高风险回归测试

现有测试覆盖面不错，但仍缺少以下关键契约：

- 备份恢复后笔记映射和重复书籍场景。
- 选择性下载暂停/恢复后 options 不丢失。
- 服务重启或 worker 异常退出后的任务接管。
- Range 请求的非法区间、空文件和尾部区间应返回正确的 `416/206`。
- 文件导入的大小限制、配额不足、同名文件和路径穿越输入。
- CORS/令牌/SSE/媒体 URL 的组合鉴权。
- 前端 `pnpm run build`、移动端窄屏、断线重连和阅读器大章节列表的浏览器自动化测试。

### P2：提升日常使用体验和维护效率

#### 6.8 任务中心增加可恢复操作

增加“重试失败任务”“打开输出目录”“查看完整日志”“复制错误详情”等操作，并把当前工具、回退工具和最终产物显示在详情中。删除任务前提供二次确认，区分“删除记录”和“删除已下载文件”。

#### 6.9 统一前后端契约与状态管理

目前页面中重复定义了多个 TypeScript `interface`，API 路径和响应结构也主要靠手写字符串维护。建议从 OpenAPI 生成 TypeScript 类型和客户端，至少集中管理 `Task/Novel/Media/Settings` 类型，降低后端字段变化造成的静默错误。

#### 6.10 提升设置与部署的可维护性

- 为 `SettingsIn` 增加范围校验（字体、行距、配额、代理 URL、AI URL）。
- 为 SQLite 引入迁移工具或版本表，避免 `create_all` 无法处理未来字段变更。
- 固定后端依赖版本并建立定期升级窗口；前端已有 lockfile，可让后端也生成可复现环境文件。
- 健康检查拆分为 liveness/readiness，readiness 可检查数据库、数据目录权限和 AI/外部工具可选状态。
- 备份导出增加压缩、分块和版本兼容策略，避免大书把整个 JSON 一次性加载到内存。

## 7. 推荐落地顺序

1. 先修复备份笔记 ID 映射，并补回归测试。
2. 给任务持久化 `options`，修复暂停/恢复竞态，再做启动接管。
3. 收紧 CORS 和令牌传递方式，明确本机/局域网部署模式。
4. 处理导入、备份和媒体下载的同步 I/O、大小限制与配额校验。
5. 统一分页响应、补索引/FTS，再改善任务日志和错误分类。
6. 最后补 OpenAPI 类型生成、迁移机制、浏览器自动化和部署文档。

## 8. 验收指标建议

| 目标 | 建议指标 |
| --- | --- |
| 备份可靠性 | 小说、章节、笔记、封面恢复成功率 100%；重复导入不产生重复笔记 |
| 任务可靠性 | 服务重启后无任务静默丢失；暂停/恢复参数一致；同一任务不重复执行 |
| 大文件体验 | 1GB 级媒体导入期间 SSE 延迟可接受，事件循环不被同步写入阻塞 |
| 搜索与列表 | 书架/资源库分页总数准确；1 万章书籍目录首屏只加载窗口数据 |
| 安全 | 未携带令牌的 API、SSE、媒体请求均按策略拒绝；令牌不出现在长期 URL/日志 |
| 可维护性 | 关键状态转换有测试；后端依赖和数据库结构可复现升级 |

