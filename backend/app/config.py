"""Application configuration: paths and runtime settings."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # /backend
PROJECT_ROOT = BASE_DIR.parent                             # project root

DATA_DIR = Path(os.environ.get("MOREAD_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "moread.db"
NOVELS_DIR = DATA_DIR / "novels"
MEDIA_DIR = DATA_DIR / "media"
DOWNLOADS_DIR = DATA_DIR / "downloads"
BACKUPS_DIR = DATA_DIR / "backups"
ARCHIVE_DIR = DATA_DIR / "archive"       # webpage archives
COVERS_DIR = DATA_DIR / "covers"

STATIC_FRONTEND_DIR = Path(os.environ.get("MOREAD_STATIC_DIR", PROJECT_ROOT / "frontend" / "dist"))

DEFAULT_STORAGE_QUOTA_GB = float(os.environ.get("MOREAD_QUOTA_GB", "20"))
DEFAULT_AI_BASE_URL = os.environ.get("MOREAD_AI_BASE_URL", "http://localhost:11434")
DEFAULT_AI_MODEL = os.environ.get("MOREAD_AI_MODEL", "llama3")

TOOLS_DIR = PROJECT_ROOT / "tools"


def ensure_dirs() -> None:
    for d in (DATA_DIR, NOVELS_DIR, MEDIA_DIR, DOWNLOADS_DIR, BACKUPS_DIR, ARCHIVE_DIR, COVERS_DIR):
        d.mkdir(parents=True, exist_ok=True)
