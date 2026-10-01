"""Application configuration: paths and runtime settings."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _app_base() -> Path:
    """Writable base for user data.

    Frozen (PyInstaller) builds keep everything portable: data lives next to
    the executable (or under %MOREAD_DATA_DIR%); in dev it stays in backend/data.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent          # /backend


def _resource_base() -> Path:
    """Read-only bundled resources (frontend build) inside a one-file exe."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent    # project root


BASE_DIR = Path(__file__).resolve().parent.parent          # /backend
PROJECT_ROOT = BASE_DIR.parent                             # project root

DATA_DIR = Path(os.environ.get("MOREAD_DATA_DIR", _app_base() / "data"))
DB_PATH = DATA_DIR / "moread.db"
NOVELS_DIR = DATA_DIR / "novels"
MEDIA_DIR = DATA_DIR / "media"
DOWNLOADS_DIR = DATA_DIR / "downloads"
BACKUPS_DIR = DATA_DIR / "backups"
ARCHIVE_DIR = DATA_DIR / "archive"       # webpage archives
COVERS_DIR = DATA_DIR / "covers"

STATIC_FRONTEND_DIR = Path(
    os.environ.get("MOREAD_STATIC_DIR", _resource_base() / "web" / "dist")
    if getattr(sys, "frozen", False)
    else os.environ.get("MOREAD_STATIC_DIR", PROJECT_ROOT / "frontend" / "dist")
)

DEFAULT_STORAGE_QUOTA_GB = float(os.environ.get("MOREAD_QUOTA_GB", "20"))
DEFAULT_AI_BASE_URL = os.environ.get("MOREAD_AI_BASE_URL", "http://localhost:11434")
DEFAULT_AI_MODEL = os.environ.get("MOREAD_AI_MODEL", "llama3")
DEFAULT_PROXY_URL = os.environ.get("MOREAD_PROXY", "")

TOOLS_DIR = _app_base() / "tools" if getattr(sys, "frozen", False) else PROJECT_ROOT / "tools"


def ensure_dirs() -> None:
    for d in (DATA_DIR, NOVELS_DIR, MEDIA_DIR, DOWNLOADS_DIR, BACKUPS_DIR, ARCHIVE_DIR, COVERS_DIR):
        d.mkdir(parents=True, exist_ok=True)
