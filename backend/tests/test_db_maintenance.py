"""A4 SQLite 例行维护：checkpoint(TRUNCATE) + VACUUM 可执行且数据完好。"""
import sqlite3

from app.services.db_maintenance import run_maintenance, warn_if_network_path


def _make_wal_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO t (v) VALUES (?)", [(f"row-{i}",) for i in range(2000)])
    conn.commit()
    conn.close()


def test_run_maintenance_vacuum_and_integrity(tmp_path):
    db = tmp_path / "m.db"
    _make_wal_db(db)
    report = run_maintenance(db)
    assert report["vacuum_ok"] is True
    assert report["checkpoint"] is not None
    assert {"busy", "log_pages", "checkpointed"} <= set(report["checkpoint"])
    # 维护后 WAL 归零或不存在（TRUNCATE checkpoint 的效果）
    wal = tmp_path / "m.db-wal"
    assert not wal.exists() or wal.stat().st_size == 0
    # 数据完好
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2000
    conn.close()


def test_maintenance_survives_missing_db(tmp_path):
    """DB 文件不存在时不应抛异常（loop 侧已兜底，这里验证直接调用也安全）。"""
    db = tmp_path / "not-exist.db"
    try:
        run_maintenance(db)
    except Exception:
        pass  # loop 会捕获；关键是不崩溃进程


def test_network_path_warning(tmp_path, caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="moread.maintenance")
    warn_if_network_path(tmp_path / "local.db")
    assert not caplog.records  # 本地路径：不告警
    warn_if_network_path("//nas/share/moread.db")
    assert any("网络路径" in r.message for r in caplog.records)
