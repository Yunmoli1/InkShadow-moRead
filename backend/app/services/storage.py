"""Storage quota & cleanup strategies."""
from __future__ import annotations

import time
from pathlib import Path

from .. import config


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def storage_stats(quota_gb: float) -> dict:
    used = dir_size(config.DATA_DIR)
    quota = int(quota_gb * 1024 * 1024 * 1024)
    return {
        "used_bytes": used,
        "quota_bytes": quota,
        "percent": round(used * 100.0 / quota, 2) if quota else 0,
        "novels_bytes": dir_size(config.NOVELS_DIR),
        "media_bytes": dir_size(config.MEDIA_DIR) + dir_size(config.DOWNLOADS_DIR),
        "backups_bytes": dir_size(config.BACKUPS_DIR),
        "db_bytes": config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0,
    }


def cleanup_candidates(older_than_days: int) -> list[Path]:
    """Finished download artifacts older than N days (novels & media stay)."""
    cutoff = time.time() - older_than_days * 86400
    out: list[Path] = []
    if not config.DOWNLOADS_DIR.exists():
        return out
    for d in config.DOWNLOADS_DIR.iterdir():
        if d.is_dir() and d.stat().st_mtime < cutoff:
            out.append(d)
    return out


def apply_cleanup(paths: list[Path]) -> tuple[int, int]:
    """Delete dirs; returns (removed_count, freed_bytes)."""
    freed = 0
    count = 0
    for p in paths:
        if p.exists():
            freed += dir_size(p)
            count += 1
            for f in sorted(p.rglob("*"), reverse=True):
                if f.is_file():
                    f.unlink(missing_ok=True)
            for d in sorted(p.rglob("*"), reverse=True):
                if d.is_dir():
                    try:
                        d.rmdir()
                    except OSError:
                        pass
            try:
                p.rmdir()
            except OSError:
                pass
    return count, freed
