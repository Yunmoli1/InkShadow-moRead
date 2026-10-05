// 自动生成：pnpm gen:api（来源 backend/app OpenAPI）——请勿手改
export interface paths {
    "/api/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tools */
        get: operations["list_tools_api_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/{tool_name}/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search With Tool */
        post: operations["search_with_tool_api_tools__tool_name__search_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Url
         * @description 预览下载目标：按 URL 自动选择工具，并尝试快速探测内容信息。
         *
         *     probe 为 None 表示该工具不支持快速探测（或探测超时），不影响下载。
         */
        post: operations["preview_url_api_tools_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/items/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Download Selected Items
         * @description 选择性下载：直接抓取用户在预览界面勾选的资源直链（图片/视频/压缩包等）。
         */
        post: operations["download_selected_items_api_tools_items_download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/auto/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Download Auto
         * @description 万能抓取：按内容类型自动挑选已安装的工具。
         */
        post: operations["download_auto_api_tools_auto_download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/{tool_name}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Download With Tool */
        post: operations["download_with_tool_api_tools__tool_name__download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools/running": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Running Tasks */
        get: operations["running_tasks_api_tools_running_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tasks */
        get: operations["list_tasks_api_tasks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Task Status Sse
         * @description SSE stream of task progress. Auto-reconnect friendly; ends at terminal state.
         */
        get: operations["task_status_sse_api_tasks__task_id__status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Task */
        get: operations["get_task_api_tasks__task_id__get"];
        put?: never;
        post?: never;
        /** Delete Task */
        delete: operations["delete_task_api_tasks__task_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause Task */
        post: operations["pause_task_api_tasks__task_id__pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume Task */
        post: operations["resume_task_api_tasks__task_id__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Retry Task
         * @description 重试失败/已取消的任务：复制原参数创建新任务（断点续传）。
         *
         *     same_tool=true 忽略回退链切换结果，用最初指定的工具重试（B3）。
         */
        post: operations["retry_task_api_tasks__task_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tasks/{task_id}/log": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Task Full Log
         * @description 完整任务日志（B3）：镜像文件全量内容，缺失时退回 DB 中的尾部日志。
         */
        get: operations["task_full_log_api_tasks__task_id__log_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Reading Stats */
        get: operations["reading_stats_api_novels_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Novels */
        get: operations["list_novels_api_novels_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/tag-list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Novel Tag List
         * @description 全部标签及数量（B1 标签筛选数据源）。
         */
        get: operations["novel_tag_list_api_novels_tag_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/download.epub": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Epub
         * @description 按需生成并下载整本书 EPUB（B2，OPDS acquisition 目标）。
         *
         *     带缓存的同步生成在后台线程执行；无章节返回 404。
         */
        get: operations["download_epub_api_novels__novel_id__download_epub_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Novels
         * @description 批量导入本地小说文件（TXT/EPUB）。
         */
        post: operations["import_novels_api_novels_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Novel */
        get: operations["get_novel_api_novels__novel_id__get"];
        put?: never;
        post?: never;
        /** Delete Novel */
        delete: operations["delete_novel_api_novels__novel_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/chapters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Chapters
         * @description 分页章节列表（配合前端 react-window 虚拟滚动）。
         */
        get: operations["list_chapters_api_novels__novel_id__chapters_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/images/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Novel Image
         * @description Serve an image extracted from an imported EPUB ([img:<name>] markers).
         */
        get: operations["novel_image_api_novels__novel_id__images__name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/chapters/{chapter_id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Chapter Content */
        get: operations["chapter_content_api_novels__novel_id__chapters__chapter_id__content_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search In Novel
         * @description 书内全文搜索：FTS5 优先（万章级 <100ms），短查询/无 FTS 回退 LIKE 扫描。
         *
         *     返回带上下文片段的命中，接口格式与旧实现一致。
         */
        get: operations["search_in_novel_api_novels__novel_id__search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Progress */
        patch: operations["update_progress_api_novels__novel_id__progress_patch"];
        trace?: never;
    };
    "/api/novels/{novel_id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Notes */
        get: operations["list_notes_api_novels__novel_id__notes_get"];
        put?: never;
        /** Create Note */
        post: operations["create_note_api_novels__novel_id__notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/notes/{note_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Note */
        delete: operations["delete_note_api_novels__novel_id__notes__note_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/ai-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ai Summary */
        post: operations["ai_summary_api_novels__novel_id__ai_summary_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/ai-summary/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ai Summary Stream
         * @description 流式 AI 摘要（SSE）：delta 增量 / end 完成 / error 友好错误。
         */
        post: operations["ai_summary_stream_api_novels__novel_id__ai_summary_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/subscribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Subscribe Novel */
        patch: operations["subscribe_novel_api_novels__novel_id__subscribe_patch"];
        trace?: never;
    };
    "/api/novels/{novel_id}/switch-source": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Switch Source
         * @description 一键换源：用新镜像 URL 重新增量抓取，完成后自动重建章节并更新来源。
         */
        post: operations["switch_source_api_novels__novel_id__switch_source_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/auto-tag": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Novels Auto Tag
         * @description 为还没有标签的书生成 AI 标签（需本地 Ollama / 外部 AI 可用）。
         */
        post: operations["novels_auto_tag_api_novels_auto_tag_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/check-update": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Novel Update */
        post: operations["check_novel_update_api_novels__novel_id__check_update_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/check-updates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check All Updates
         * @description 检查所有订阅书（跳过 6 小时内已检查的）。
         */
        post: operations["check_all_updates_api_novels_check_updates_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/reading-session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Log Reading Session */
        post: operations["log_reading_session_api_novels__novel_id__reading_session_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Media */
        get: operations["list_media_api_media_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/tag-list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Media Tag List
         * @description 全部标签及数量（B1 标签筛选数据源）。
         */
        get: operations["media_tag_list_api_media_tag_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/batch-import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Batch Import */
        post: operations["batch_import_api_media_batch_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/{media_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Media Detail */
        get: operations["media_detail_api_media__media_id__get"];
        put?: never;
        post?: never;
        /** Delete Media */
        delete: operations["delete_media_api_media__media_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/{media_id}/thumb": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Media Thumb
         * @description 缩略图（视频首帧 / 图片压缩版）；无缩略图时 404，前端回退原图。
         */
        get: operations["media_thumb_api_media__media_id__thumb_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/{media_id}/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Media Progress
         * @description 记录/查询音视频播放进度（秒），存于 extra。
         */
        patch: operations["media_progress_api_media__media_id__progress_patch"];
        trace?: never;
    };
    "/api/media/auto-tag": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Media Auto Tag
         * @description 为还没有标签的媒体生成 AI 标签。
         */
        post: operations["media_auto_tag_api_media_auto_tag_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/backfill-assets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Backfill Assets
         * @description 为缺少时长/缩略图的既有资源补建（视频时长+首帧、图片缩略图）。
         */
        post: operations["backfill_assets_api_media_backfill_assets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/{media_id}/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Media File
         * @description Serve file bytes with HTTP Range support (video/audio seeking).
         */
        get: operations["media_file_api_media__media_id__file_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/{media_id}/extract-article": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Extract Article From Media
         * @description 把已归档网页（page 类型）的正文提取为"文章"入书架，返回小说信息。
         */
        post: operations["extract_article_from_media_api_media__media_id__extract_article_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/types/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Types Summary */
        get: operations["types_summary_api_media_types_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_api_settings_get"];
        /** Update Settings */
        put: operations["update_settings_api_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/storage/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Storage Stats */
        get: operations["storage_stats_api_storage_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/storage/cleanup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Storage Cleanup
         * @description 删除超过 N 天的已完成下载目录（书库与媒体库不受影响）。
         */
        post: operations["storage_cleanup_api_storage_cleanup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backup/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Backup Export
         * @description v2 完整备份：正文（含大书的磁盘文件内容）、封面、EPUB 图片全部内联。
         */
        get: operations["backup_export_api_backup_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backup/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Backup Import
         * @description Accept decrypted backup JSON. v3（含笔记映射）/ v2 / v1 均可。
         */
        post: operations["backup_import_api_backup_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Global Search */
        get: operations["global_search_api_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metrics */
        get: operations["metrics_api_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/opds": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Opds Root */
        get: operations["opds_root_opds_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/opds/books": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Opds Books */
        get: operations["opds_books_opds_books_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/novels/{novel_id}/download.txt": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Txt
         * @description 整本书 TXT 流式下载（OPDS acquisition 目标）。
         */
        get: operations["_download_txt_api_novels__novel_id__download_txt_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Liveness：进程活着即可响应，不检查任何依赖。
         */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Ready
         * @description Readiness：DB 可查询 + 数据目录可写。不可用时返回 503（编排层据此摘流量）。
         *
         *     注意：本端点固定免令牌，便于探针/负载均衡器调用。
         */
        get: operations["health_ready_api_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AiSummaryIn */
        AiSummaryIn: {
            /** Chapter Id */
            chapter_id: string;
        };
        /** AiSummaryOut */
        AiSummaryOut: {
            /** Novel Id */
            novel_id: string;
            /** Chapter Id */
            chapter_id: string;
            /** Summary */
            summary: string;
            /** Model */
            model: string;
            /**
             * Cached
             * @default false
             */
            cached: boolean;
        };
        /** Body_batch_import_api_media_batch_import_post */
        Body_batch_import_api_media_batch_import_post: {
            /** Files */
            files: string[];
        };
        /** Body_import_novels_api_novels_import_post */
        Body_import_novels_api_novels_import_post: {
            /** Files */
            files: string[];
        };
        /** ChapterContentOut */
        ChapterContentOut: {
            /** Id */
            id: string;
            /** Idx */
            idx: number;
            /** Title */
            title: string;
            /** Content */
            content: string;
            /** Word Count */
            word_count: number;
            /** Novel Id */
            novel_id: string;
        };
        /** ChapterOut */
        ChapterOut: {
            /** Id */
            id: string;
            /** Idx */
            idx: number;
            /** Title */
            title: string;
            /** Word Count */
            word_count: number;
        };
        /** ChapterPage */
        ChapterPage: {
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
            /** Items */
            items: components["schemas"]["ChapterOut"][];
        };
        /** DownloadCreated */
        DownloadCreated: {
            /** Task Id */
            task_id: string;
            /** Tool */
            tool: string;
            /** Status */
            status: string;
            /**
             * Message
             * @default
             */
            message: string;
        };
        /** DownloadItemsIn */
        DownloadItemsIn: {
            /** Urls */
            urls: string[];
        };
        /** DownloadRequest */
        DownloadRequest: {
            /** Url */
            url: string;
            /**
             * Content Type
             * @default auto
             */
            content_type: string;
            /** Tool */
            tool?: string | null;
            /** Options */
            options?: {
                [key: string]: unknown;
            };
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImportResult */
        ImportResult: {
            /** Imported */
            imported: string[];
            /** Skipped */
            skipped: string[];
            /** Errors */
            errors: string[];
        };
        /** MediaOut */
        MediaOut: {
            /** Id */
            id: string;
            /** Media Type */
            media_type: string;
            /** Title */
            title: string;
            /** Source Url */
            source_url: string;
            /** File Path */
            file_path: string;
            /** Thumbnail Path */
            thumbnail_path: string;
            /** Mime Type */
            mime_type: string;
            /** File Size */
            file_size: number;
            /** Duration */
            duration: number;
            /**
             * Preview Url
             * @default
             */
            preview_url: string;
            /**
             * Thumbnail Url
             * @default
             */
            thumbnail_url: string;
            /**
             * Tags
             * @default []
             */
            tags: unknown[];
            /**
             * Extra
             * @default {}
             */
            extra: {
                [key: string]: unknown;
            };
            /** Created At */
            created_at?: string | null;
        };
        /** NoteIn */
        NoteIn: {
            /** Chapter Id */
            chapter_id?: string | null;
            /**
             * Chapter Title
             * @default
             */
            chapter_title: string;
            /**
             * Chapter Idx
             * @default 0
             */
            chapter_idx: number;
            /**
             * Excerpt
             * @default
             */
            excerpt: string;
            /**
             * Content
             * @default
             */
            content: string;
        };
        /** NoteOut */
        NoteOut: {
            /** Id */
            id: string;
            /** Novel Id */
            novel_id: string;
            /** Chapter Id */
            chapter_id: string | null;
            /** Chapter Title */
            chapter_title: string;
            /** Chapter Idx */
            chapter_idx: number;
            /** Excerpt */
            excerpt: string;
            /** Content */
            content: string;
            /** Created At */
            created_at?: string | null;
        };
        /** NovelOut */
        NovelOut: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Author */
            author: string;
            /** Source Url */
            source_url: string;
            /** Description */
            description: string;
            /** Cover Path */
            cover_path: string;
            /** File Type */
            file_type: string;
            /** Category */
            category: string;
            /** Total Chapters */
            total_chapters: number;
            /** Read Chapters */
            read_chapters: number;
            /** Last Chapter Idx */
            last_chapter_idx: number;
            /** Last Scroll Pos */
            last_scroll_pos: number;
            /** File Size */
            file_size: number;
            /**
             * Subscribed
             * @default false
             */
            subscribed: boolean;
            /**
             * New Chapters
             * @default 0
             */
            new_chapters: number;
            /**
             * Tags
             * @default []
             */
            tags: unknown[];
            /** Created At */
            created_at?: string | null;
            /** Updated At */
            updated_at?: string | null;
        };
        /** PreviewRequest */
        PreviewRequest: {
            /** Url */
            url: string;
            /**
             * Content Type
             * @default auto
             */
            content_type: string;
            /** Tool */
            tool?: string | null;
        };
        /** ProgressIn */
        ProgressIn: {
            /**
             * Chapter Idx
             * @default 0
             */
            chapter_idx: number;
            /**
             * Scroll Pos
             * @default 0
             */
            scroll_pos: number;
            /**
             * Duration Sec
             * @default 0
             */
            duration_sec: number;
            /**
             * Chapters Read
             * @default 1
             */
            chapters_read: number;
        };
        /** ReadingSessionIn */
        ReadingSessionIn: {
            /** Duration Sec */
            duration_sec: number;
            /**
             * Chapters Read
             * @default 0
             */
            chapters_read: number;
        };
        /** SearchAllOut */
        SearchAllOut: {
            /** Novels */
            novels: {
                [key: string]: unknown;
            }[];
            /** Media */
            media: {
                [key: string]: unknown;
            }[];
        };
        /** SearchRequest */
        SearchRequest: {
            /** Query */
            query: string;
            /**
             * Limit
             * @default 8
             */
            limit: number;
        };
        /** SearchResult */
        SearchResult: {
            /** Tool */
            tool: string;
            /** Results */
            results: {
                [key: string]: unknown;
            }[];
            /**
             * Message
             * @default
             */
            message: string;
        };
        /** SettingsIn */
        SettingsIn: {
            /** Theme */
            theme?: string | null;
            /** Ai Base Url */
            ai_base_url?: string | null;
            /** Ai Model */
            ai_model?: string | null;
            /** Ai Style */
            ai_style?: string | null;
            /** Ai Api Key */
            ai_api_key?: string | null;
            /** Proxy Url */
            proxy_url?: string | null;
            /** Storage Quota Gb */
            storage_quota_gb?: number | null;
            /** Reader Font Size */
            reader_font_size?: number | null;
            /** Reader Line Height */
            reader_line_height?: number | null;
            /** Reader Paper */
            reader_paper?: string | null;
            /** Reader Mode */
            reader_mode?: string | null;
            /** Access Token */
            access_token?: string | null;
        };
        /** SettingsOut */
        SettingsOut: {
            /**
             * Theme
             * @default light
             */
            theme: string;
            /** Ai Base Url */
            ai_base_url: string;
            /** Ai Model */
            ai_model: string;
            /**
             * Ai Style
             * @default ollama
             */
            ai_style: string;
            /**
             * Ai Api Key
             * @default
             */
            ai_api_key: string;
            /**
             * Proxy Url
             * @default
             */
            proxy_url: string;
            /** Storage Quota Gb */
            storage_quota_gb: number;
            /**
             * Reader Font Size
             * @default 18
             */
            reader_font_size: number;
            /**
             * Reader Line Height
             * @default 1.8
             */
            reader_line_height: number;
            /**
             * Reader Paper
             * @default paper
             */
            reader_paper: string;
            /**
             * Reader Mode
             * @default scroll
             */
            reader_mode: string;
            /**
             * Access Token
             * @default
             */
            access_token: string;
        };
        /** SubscribeIn */
        SubscribeIn: {
            /** Subscribed */
            subscribed: boolean;
        };
        /** SwitchSourceIn */
        SwitchSourceIn: {
            /** New Url */
            new_url: string;
        };
        /** TaskOut */
        TaskOut: {
            /** Id */
            id: string;
            /** Tool */
            tool: string;
            /** Task Type */
            task_type: string;
            /** Url */
            url: string;
            /** Title */
            title: string;
            /** Status */
            status: string;
            /** Progress */
            progress: number;
            /** Speed */
            speed: string;
            /** Eta */
            eta: string;
            /** Message */
            message: string;
            /** Dest Type */
            dest_type: string;
            /** Output Dir */
            output_dir: string;
            /**
             * Options
             * @default {}
             */
            options: {
                [key: string]: unknown;
            };
            /**
             * Log Tail
             * @default []
             */
            log_tail: string[];
            /**
             * Error Code
             * @default
             */
            error_code: string;
            /**
             * Retry Count
             * @default 0
             */
            retry_count: number;
            /**
             * Fallback Chain
             * @default []
             */
            fallback_chain: string[];
            /** Created At */
            created_at?: string | null;
            /** Started At */
            started_at?: string | null;
            /** Finished At */
            finished_at?: string | null;
        };
        /** TaskPage */
        TaskPage: {
            /** Items */
            items: components["schemas"]["TaskOut"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
        };
        /** ToolOut */
        ToolOut: {
            /** Name */
            name: string;
            /** Display */
            display: string;
            /** Category */
            category: string;
            /** Installed */
            installed: boolean;
            /** Version */
            version?: string | null;
            /** Install Hint */
            install_hint: string;
            /** Supports Search */
            supports_search: boolean;
            /** Content Types */
            content_types: string[];
            /**
             * Docs Url
             * @default
             */
            docs_url: string;
            /**
             * Remark
             * @default
             */
            remark: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_tools_api_tools_get: {
        parameters: {
            query?: {
                refresh?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_with_tool_api_tools__tool_name__search_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_url_api_tools_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_selected_items_api_tools_items_download_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DownloadItemsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_auto_api_tools_auto_download_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DownloadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_with_tool_api_tools__tool_name__download_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DownloadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    running_tasks_api_tools_running_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    list_tasks_api_tasks_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                status?: string | null;
                tool?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    task_status_sse_api_tasks__task_id__status_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_task_api_tasks__task_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_task_api_tasks__task_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pause_task_api_tasks__task_id__pause_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_task_api_tasks__task_id__resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_task_api_tasks__task_id__retry_post: {
        parameters: {
            query?: {
                same_tool?: boolean;
            };
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    task_full_log_api_tasks__task_id__log_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reading_stats_api_novels_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_novels_api_novels_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                search?: string | null;
                category?: string | null;
                tag?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    novel_tag_list_api_novels_tag_list_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    download_epub_api_novels__novel_id__download_epub_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_novels_api_novels_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_novels_api_novels_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_novel_api_novels__novel_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NovelOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_novel_api_novels__novel_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_chapters_api_novels__novel_id__chapters_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChapterPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    novel_image_api_novels__novel_id__images__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chapter_content_api_novels__novel_id__chapters__chapter_id__content_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
                chapter_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChapterContentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_in_novel_api_novels__novel_id__search_get: {
        parameters: {
            query: {
                q: string;
            };
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_progress_api_novels__novel_id__progress_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProgressIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_notes_api_novels__novel_id__notes_get: {
        parameters: {
            query?: {
                chapter_idx?: number | null;
            };
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NoteOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_note_api_novels__novel_id__notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NoteIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NoteOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_note_api_novels__novel_id__notes__note_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
                note_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ai_summary_api_novels__novel_id__ai_summary_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiSummaryIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AiSummaryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ai_summary_stream_api_novels__novel_id__ai_summary_stream_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiSummaryIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    subscribe_novel_api_novels__novel_id__subscribe_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubscribeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    switch_source_api_novels__novel_id__switch_source_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SwitchSourceIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    novels_auto_tag_api_novels_auto_tag_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    check_novel_update_api_novels__novel_id__check_update_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_all_updates_api_novels_check_updates_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    log_reading_session_api_novels__novel_id__reading_session_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReadingSessionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_media_api_media_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                /** @description image/video/audio/page/doc */
                media_type?: string | null;
                search?: string | null;
                tag?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    media_tag_list_api_media_tag_list_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    batch_import_api_media_batch_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_batch_import_api_media_batch_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    media_detail_api_media__media_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MediaOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_media_api_media__media_id__delete: {
        parameters: {
            query?: {
                delete_file?: boolean;
            };
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    media_thumb_api_media__media_id__thumb_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    media_progress_api_media__media_id__progress_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    media_auto_tag_api_media_auto_tag_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    backfill_assets_api_media_backfill_assets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    media_file_api_media__media_id__file_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    extract_article_from_media_api_media__media_id__extract_article_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                media_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    types_summary_api_media_types_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_settings_api_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
        };
    };
    update_settings_api_settings_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    storage_stats_api_storage_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    storage_cleanup_api_storage_cleanup_post: {
        parameters: {
            query?: {
                older_than_days?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    backup_export_api_backup_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    backup_import_api_backup_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    global_search_api_search_get: {
        parameters: {
            query: {
                q: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchAllOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_api_metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    opds_root_opds_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    opds_books_opds_books_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    _download_txt_api_novels__novel_id__download_txt_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                novel_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    health_ready_api_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
