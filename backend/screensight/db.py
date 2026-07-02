# 文件路径：backend/screensight/db.py
# 文件作用：SQLite 数据库连接管理、schema 初始化与 sqlite-vec 扩展加载
# 最后更新时间：2026-07-02-1209

"""数据库连接与初始化。

使用 SQLite + sqlite-vec 扩展，单文件存储结构化数据与向量数据。
启用 WAL 模式提升并发读写。
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH, ensure_dirs


# 数据库 schema DDL（与 ARCHITECTURE.md 第 3 节一致）
SCHEMA_SQL = """
-- 截图记录：每次截屏一条
CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,             -- ISO8601 时间戳
    monitor_index INTEGER NOT NULL,        -- 显示器序号
    is_focused BOOLEAN NOT NULL,           -- 是否焦点屏
    archive_path TEXT,                     -- 存档图路径（低质量压缩）
    width INTEGER,
    height INTEGER,
    recognition_status TEXT NOT NULL DEFAULT 'pending',  -- pending/success/failed/skipped
    recognition_id INTEGER,                -- 关联 recognitions.id
    created_at TEXT NOT NULL
);

-- 识别结果：VLM 返回的结构化数据
CREATE TABLE IF NOT EXISTS recognitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL,
    category TEXT NOT NULL,                -- 一级类别（23类之一）
    sub_desc TEXT,                         -- 二级动态描述
    object_name TEXT,                      -- 项目/对象名
    activity TEXT,                         -- 一句话活动描述
    confidence REAL NOT NULL,              -- 0-1
    is_low_confidence BOOLEAN NOT NULL DEFAULT 0,
    raw_response TEXT,                     -- VLM 原始返回（调试用）
    llm_tokens_used INTEGER DEFAULT 0,     -- token 用量（费用统计）
    llm_cost_estimate REAL DEFAULT 0,      -- 预估费用
    created_at TEXT NOT NULL,
    FOREIGN KEY (capture_id) REFERENCES captures(id)
);

-- 活动时段：合并连续同类识别结果
CREATE TABLE IF NOT EXISTS activity_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    category TEXT NOT NULL,
    sub_desc TEXT,
    object_name TEXT,
    capture_ids TEXT NOT NULL,             -- JSON 数组：含的截图 ID
    capture_count INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_low_confidence BOOLEAN NOT NULL DEFAULT 0,
    is_closed BOOLEAN NOT NULL DEFAULT 0,  -- 是否已结束（增量合并用）
    created_at TEXT NOT NULL
);

-- 报告
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,             -- hourly/daily/weekly/monthly
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    stats_json TEXT NOT NULL,              -- 规则统计结果（JSON）
    llm_summary TEXT,                      -- LLM 润色后的自然语言总结
    generated_at TEXT NOT NULL,
    is_manual BOOLEAN NOT NULL DEFAULT 0
);

-- 配置/设置
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 费用统计聚合
CREATE TABLE IF NOT EXISTS usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,               -- YYYY-MM-DD
    api_type TEXT NOT NULL,                -- vlm/llm/embedding
    call_count INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost_estimate REAL NOT NULL,
    UNIQUE(stat_date, api_type)
);

-- 费用统计聚合（小时粒度，用于趋势图与单小时成本）
CREATE TABLE IF NOT EXISTS usage_stats_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_hour TEXT NOT NULL,               -- YYYY-MM-DD HH:00
    api_type TEXT NOT NULL,                -- vlm/llm/embedding
    call_count INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost_estimate REAL NOT NULL,
    UNIQUE(stat_hour, api_type)
);

-- 全文搜索索引（识别描述+报告文本+标签对象名）
-- 使用 trigram 分词器，对中文支持好（按三字组切分）
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    content,
    source_type,        -- recognition/report
    source_id,
    tokenize='trigram'
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON captures(captured_at);
CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(recognition_status);
CREATE INDEX IF NOT EXISTS idx_recognitions_category ON recognitions(category);
CREATE INDEX IF NOT EXISTS idx_recognitions_object ON recognitions(object_name);
CREATE INDEX IF NOT EXISTS idx_recognitions_confidence ON recognitions(confidence);
CREATE INDEX IF NOT EXISTS idx_segments_start ON activity_segments(start_time);
CREATE INDEX IF NOT EXISTS idx_segments_category ON activity_segments(category);
CREATE INDEX IF NOT EXISTS idx_segments_closed ON activity_segments(is_closed);
CREATE INDEX IF NOT EXISTS idx_reports_type_period ON reports(report_type, period_start);
CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_stats(stat_date, api_type);
CREATE INDEX IF NOT EXISTS idx_usage_hour ON usage_stats_hourly(stat_hour, api_type);
"""


def _load_vec_extension(conn: sqlite3.Connection) -> None:
    """加载 sqlite-vec 扩展并创建向量虚拟表。"""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        # sqlite-vec 不可用时跳过向量表创建，不影响核心功能
        return
    # 向量表（1024 维，与 bge-large-zh 一致）
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS recognition_vectors USING vec0("
        "recognition_id INTEGER PRIMARY KEY, embedding FLOAT[1024])"
    )


def init_db(db_path: Path | None = None) -> None:
    """初始化数据库 schema。幂等，可重复调用。"""
    ensure_dirs()
    path = db_path or DB_PATH
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(INDEXES_SQL)
        _load_vec_extension(conn)
        conn.commit()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """获取数据库连接（WAL 模式 + 外键约束）。

    注意：sqlite-vec 扩展每次连接需重新加载。
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _load_vec_extension(conn)
    return conn


# 线程安全的连接池（单连接 + 互斥锁，足够本工具并发量）
_local = threading.local()

# 当前数据库路径（可被 set_db_path 覆盖，用于测试）
_current_db_path: Optional[Path] = None


def set_db_path(path: Path | str | None) -> None:
    """设置当前数据库路径（测试时指向临时库）。

    切换后已有连接会被清空，下次 get_db() 重新连接新路径。
    """
    global _current_db_path
    _current_db_path = Path(path) if path else None
    # 清空线程本地连接
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def get_active_db_path() -> Path:
    """获取当前生效的数据库路径。"""
    return _current_db_path or DB_PATH


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """获取数据库连接的上下文管理器。

    使用线程本地连接复用，避免频繁创建。
    """
    path = get_active_db_path()
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = get_connection(path)
    try:
        yield _local.conn
        _local.conn.commit()
    except Exception:
        _local.conn.rollback()
        raise
