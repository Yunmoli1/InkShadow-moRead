"""Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ToolOut(BaseModel):
    name: str
    display: str
    category: str
    installed: bool
    version: str | None = None
    install_hint: str
    supports_search: bool
    content_types: list[str]
    docs_url: str = ""
    remark: str = ""


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=8, ge=1, le=30)


class SearchResult(BaseModel):
    tool: str
    results: list[dict]
    message: str = ""


class DownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    content_type: str = "auto"       # auto/image/video/audio/page/novel
    tool: str | None = None          # explicit tool name; else auto-pick
    options: dict = Field(default_factory=dict)


class DownloadCreated(BaseModel):
    task_id: str
    tool: str
    status: str
    message: str = ""


class TaskOut(BaseModel):
    id: str
    tool: str
    task_type: str
    url: str
    title: str
    status: str
    progress: float
    speed: str
    eta: str
    message: str
    dest_type: str
    output_dir: str
    log_tail: list[str] = []
    created_at: datetime | None = None
    finished_at: datetime | None = None


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class NovelOut(BaseModel):
    id: str
    title: str
    author: str
    source_url: str
    description: str
    cover_path: str
    file_type: str
    category: str
    total_chapters: int
    read_chapters: int
    last_chapter_idx: int
    last_scroll_pos: float
    file_size: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChapterOut(BaseModel):
    id: str
    idx: int
    title: str
    word_count: int


class ChapterContentOut(BaseModel):
    id: str
    idx: int
    title: str
    content: str
    word_count: int
    novel_id: str


class ProgressIn(BaseModel):
    chapter_idx: int = 0
    scroll_pos: float = 0.0
    duration_sec: int = 0
    chapters_read: int = 1


class NoteIn(BaseModel):
    chapter_id: str | None = None
    chapter_title: str = ""
    chapter_idx: int = 0
    excerpt: str = ""
    content: str = ""


class NoteOut(BaseModel):
    id: str
    novel_id: str
    chapter_id: str | None
    chapter_title: str
    chapter_idx: int
    excerpt: str
    content: str
    created_at: datetime | None = None


class MediaOut(BaseModel):
    id: str
    media_type: str
    title: str
    source_url: str
    file_path: str
    thumbnail_path: str
    mime_type: str
    file_size: int
    duration: float
    preview_url: str = ""
    extra: dict = {}
    created_at: datetime | None = None


class ImportResult(BaseModel):
    imported: list[str]
    skipped: list[str]
    errors: list[str]


class AiSummaryIn(BaseModel):
    chapter_id: str


class AiSummaryOut(BaseModel):
    novel_id: str
    chapter_id: str
    summary: str
    model: str
    cached: bool = False


class SettingsOut(BaseModel):
    theme: str = "light"
    ai_base_url: str
    ai_model: str
    ai_style: str = "ollama"
    ai_api_key: str = ""
    storage_quota_gb: float
    reader_font_size: int = 18
    reader_line_height: float = 1.8
    reader_paper: str = "paper"
    reader_mode: str = "scroll"


class SettingsIn(BaseModel):
    theme: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_style: str | None = None
    ai_api_key: str | None = None
    storage_quota_gb: float | None = None
    reader_font_size: int | None = None
    reader_line_height: float | None = None
    reader_paper: str | None = None
    reader_mode: str | None = None


class ReadingSessionIn(BaseModel):
    duration_sec: int = Field(ge=0, le=86400)
    chapters_read: int = Field(default=0, ge=0)


class SearchAllOut(BaseModel):
    novels: list[dict]
    media: list[dict]
