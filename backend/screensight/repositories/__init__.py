# 文件路径：backend/screensight/repositories/__init__.py
# 文件作用：数据访问层，封装 captures/recognitions/segments/settings 的 CRUD
# 最后更新时间：2026-06-28-1959

"""数据访问层。

所有数据库读写集中于此，业务服务层通过仓储接口操作数据，
避免 SQL 散落在各服务中。时间统一使用 ISO8601 字符串（本地时区 +08:00）。
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

from ..db import get_db
from ..infra.timeutil import now_iso, today_str, iso_to_dt


@dataclass
class CaptureRecord:
    id: Optional[int]
    captured_at: str
    monitor_index: int
    is_focused: bool
    archive_path: Optional[str]
    width: Optional[int]
    height: Optional[int]
    recognition_status: str
    recognition_id: Optional[int]


@dataclass
class RecognitionRecord:
    id: Optional[int]
    capture_id: int
    category: str
    sub_desc: str
    object_name: str
    activity: str
    confidence: float
    is_low_confidence: bool
    raw_response: str
    llm_tokens_used: int
    llm_cost_estimate: float
    created_at: str


@dataclass
class SegmentRecord:
    id: Optional[int]
    start_time: str
    end_time: str
    category: str
    sub_desc: str
    object_name: str
    capture_ids: list[int]
    capture_count: int
    duration_seconds: int
    is_low_confidence: bool
    is_closed: bool


# ============ Captures ============

def insert_capture(
    captured_at: str,
    monitor_index: int,
    is_focused: bool,
    width: int,
    height: int,
    archive_path: Optional[str] = None,
    recognition_status: str = "pending",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """插入一条截图记录，返回 id。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        cur = conn.execute(
            """INSERT INTO captures
               (captured_at, monitor_index, is_focused, archive_path, width, height,
                recognition_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (captured_at, monitor_index, int(is_focused), archive_path, width, height,
             recognition_status, now_iso()),
        )
        return cur.lastrowid
    finally:
        if own_conn:
            conn.commit()


def update_capture_recognition(
    capture_id: int,
    status: str,
    recognition_id: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """更新截图的识别状态与关联。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        conn.execute(
            "UPDATE captures SET recognition_status=?, recognition_id=? WHERE id=?",
            (status, recognition_id, capture_id),
        )
    finally:
        if own_conn:
            conn.commit()


def get_capture(capture_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute("SELECT * FROM captures WHERE id=?", (capture_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            conn.commit()


# ============ Recognitions ============

def insert_recognition(
    capture_id: int,
    category: str,
    sub_desc: str,
    object_name: str,
    activity: str,
    confidence: float,
    is_low_confidence: bool,
    raw_response: str,
    llm_tokens_used: int = 0,
    llm_cost_estimate: float = 0.0,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """插入识别结果，返回 id。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        cur = conn.execute(
            """INSERT INTO recognitions
               (capture_id, category, sub_desc, object_name, activity, confidence,
                is_low_confidence, raw_response, llm_tokens_used, llm_cost_estimate, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (capture_id, category, sub_desc, object_name, activity, confidence,
             int(is_low_confidence), raw_response, llm_tokens_used, llm_cost_estimate, now_iso()),
        )
        return cur.lastrowid
    finally:
        if own_conn:
            conn.commit()


def get_recognition(recognition_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute("SELECT * FROM recognitions WHERE id=?", (recognition_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            conn.commit()


def insert_recognition_vector(
    recognition_id: int,
    embedding: list[float],
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """插入识别结果向量。返回是否成功（sqlite-vec 不可用时返回 False）。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        # sqlite-vec 接受 JSON 数组字符串
        vec_str = json.dumps(embedding)
        conn.execute(
            "INSERT INTO recognition_vectors(recognition_id, embedding) VALUES (?, ?)",
            (recognition_id, vec_str),
        )
        return True
    except Exception:
        return False
    finally:
        if own_conn:
            conn.commit()


def search_similar_recognitions(
    query_embedding: list[float],
    top_k: int = 8,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """向量相似度检索，返回 top-K 识别记录。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        vec_str = json.dumps(query_embedding)
        # sqlite-vec 要求 KNN 查询的 LIMIT 直接作用于 vec0 表，
        # 故先用子查询检索 top-K，再 JOIN recognitions 取详情。
        rows = conn.execute(
            """SELECT v.recognition_id AS vec_recognition_id, v.distance,
                      rec.id, rec.capture_id, rec.category, rec.sub_desc,
                      rec.object_name, rec.activity, rec.confidence,
                      rec.is_low_confidence, rec.created_at
               FROM (
                   SELECT recognition_id, distance
                   FROM recognition_vectors
                   WHERE embedding MATCH ?
                   ORDER BY distance
                   LIMIT ?
               ) v
               JOIN recognitions rec ON rec.id = v.recognition_id
               ORDER BY v.distance""",
            (vec_str, top_k),
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        if own_conn:
            conn.commit()


# ============ Activity Segments ============

def get_open_segment(
    category: str,
    object_name: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[SegmentRecord]:
    """获取指定类别+对象的未关闭时段（用于增量合并）。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute(
            """SELECT * FROM activity_segments
               WHERE category=? AND object_name=? AND is_closed=0
               ORDER BY id DESC LIMIT 1""",
            (category, object_name if object_name else ""),
        ).fetchone()
        if not row:
            return None
        return _row_to_segment(dict(row))
    finally:
        if own_conn:
            conn.commit()


def insert_segment(
    start_time: str,
    category: str,
    sub_desc: str,
    object_name: str,
    capture_ids: list[int],
    is_low_confidence: bool = False,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """新建活动时段，返回 id。end_time 初始等于 start_time。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        cur = conn.execute(
            """INSERT INTO activity_segments
               (start_time, end_time, category, sub_desc, object_name,
                capture_ids, capture_count, duration_seconds, is_low_confidence,
                is_closed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (start_time, start_time, category, sub_desc,
             object_name if object_name else "",
             json.dumps(capture_ids), len(capture_ids), 0,
             int(is_low_confidence), now_iso()),
        )
        return cur.lastrowid
    finally:
        if own_conn:
            conn.commit()


def update_segment_append(
    segment_id: int,
    end_time: str,
    new_capture_id: int,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """向时段追加一条截图，更新 end_time 与 capture_ids。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute(
            "SELECT capture_ids, start_time FROM activity_segments WHERE id=?",
            (segment_id,),
        ).fetchone()
        if not row:
            return
        ids = json.loads(row["capture_ids"])
        ids.append(new_capture_id)
        start_dt = iso_to_dt(row["start_time"])
        end_dt = iso_to_dt(end_time)
        duration = int((end_dt - start_dt).total_seconds())
        conn.execute(
            """UPDATE activity_segments
               SET end_time=?, capture_ids=?, capture_count=?, duration_seconds=?
               WHERE id=?""",
            (end_time, json.dumps(ids), len(ids), duration, segment_id),
        )
    finally:
        if own_conn:
            conn.commit()


def close_segment(segment_id: int, conn: Optional[sqlite3.Connection] = None) -> None:
    """关闭时段。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        conn.execute("UPDATE activity_segments SET is_closed=1 WHERE id=?", (segment_id,))
    finally:
        if own_conn:
            conn.commit()


def set_segment_end(segment_id: int, end_time: str,
                    conn: Optional[sqlite3.Connection] = None) -> None:
    """显式设置时段结束时间并重算时长（关闭时段时使用）。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute(
            "SELECT start_time FROM activity_segments WHERE id=?", (segment_id,)
        ).fetchone()
        if not row:
            return
        start_dt = iso_to_dt(row["start_time"])
        end_dt = iso_to_dt(end_time)
        duration = max(0, int((end_dt - start_dt).total_seconds()))
        conn.execute(
            "UPDATE activity_segments SET end_time=?, duration_seconds=?, is_closed=1 WHERE id=?",
            (end_time, duration, segment_id),
        )
    finally:
        if own_conn:
            conn.commit()


def close_all_open_segments(conn: Optional[sqlite3.Connection] = None) -> int:
    """关闭所有未关闭时段（如暂停/锁屏时），返回关闭数。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        cur = conn.execute("UPDATE activity_segments SET is_closed=1 WHERE is_closed=0")
        return cur.rowcount
    finally:
        if own_conn:
            conn.commit()


def query_segments(
    start: Optional[str] = None,
    end: Optional[str] = None,
    category: Optional[str] = None,
    object_name: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 1000,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    """查询活动时段（支持多维筛选）。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        sql = """SELECT s.*, r.confidence FROM activity_segments s
                 LEFT JOIN recognitions r ON r.capture_id =
                   (SELECT value FROM json_each(s.capture_ids) LIMIT 1)
                 WHERE 1=1"""
        params: list[Any] = []
        if start:
            sql += " AND s.start_time >= ?"
            params.append(start)
        if end:
            sql += " AND s.start_time < ?"
            params.append(end)
        if category:
            sql += " AND s.category = ?"
            params.append(category)
        if object_name:
            sql += " AND s.object_name = ?"
            params.append(object_name)
        if min_confidence is not None:
            sql += " AND (r.confidence IS NULL OR r.confidence >= ?)"
            params.append(min_confidence)
        sql += " ORDER BY s.start_time ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.commit()


def delete_segment(segment_id: int, conn: Optional[sqlite3.Connection] = None) -> list[str]:
    """删除时段及其关联的截图/识别/向量。返回被删截图的文件路径列表。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute(
            "SELECT capture_ids FROM activity_segments WHERE id=?", (segment_id,)
        ).fetchone()
        if not row:
            return []
        capture_ids = json.loads(row["capture_ids"])
        # 收集截图文件路径
        paths: list[str] = []
        if capture_ids:
            placeholders = ",".join("?" * len(capture_ids))
            path_rows = conn.execute(
                f"SELECT archive_path FROM captures WHERE id IN ({placeholders})",
                capture_ids,
            ).fetchall()
            paths = [r["archive_path"] for r in path_rows if r["archive_path"]]
        # 删除向量
        for cid in capture_ids:
            conn.execute(
                "DELETE FROM recognition_vectors WHERE recognition_id IN "
                "(SELECT recognition_id FROM captures WHERE id=?)", (cid,)
            )
        # 删除识别
        if capture_ids:
            placeholders = ",".join("?" * len(capture_ids))
            conn.execute(
                f"DELETE FROM recognitions WHERE capture_id IN ({placeholders})",
                capture_ids,
            )
            # 删除截图记录
            conn.execute(
                f"DELETE FROM captures WHERE id IN ({placeholders})",
                capture_ids,
            )
        # 删除时段
        conn.execute("DELETE FROM activity_segments WHERE id=?", (segment_id,))
        return paths
    finally:
        if own_conn:
            conn.commit()


def _row_to_segment(row: dict) -> SegmentRecord:
    return SegmentRecord(
        id=row["id"], start_time=row["start_time"], end_time=row["end_time"],
        category=row["category"], sub_desc=row.get("sub_desc") or "",
        object_name=row.get("object_name") or "",
        capture_ids=json.loads(row["capture_ids"]),
        capture_count=row["capture_count"], duration_seconds=row["duration_seconds"],
        is_low_confidence=bool(row["is_low_confidence"]),
        is_closed=bool(row["is_closed"]),
    )


# ============ Settings ============

def get_setting(key: str, default: Optional[str] = None,
                conn: Optional[sqlite3.Connection] = None) -> Optional[str]:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        if own_conn:
            conn.commit()


def set_setting(key: str, value: str, conn: Optional[sqlite3.Connection] = None) -> None:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        conn.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, now_iso()),
        )
    finally:
        if own_conn:
            conn.commit()


def get_all_settings(conn: Optional[sqlite3.Connection] = None) -> dict[str, str]:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        if own_conn:
            conn.commit()


# ============ Usage Stats ============

def record_usage(
    api_type: str,
    call_count: int,
    tokens_used: int,
    cost_estimate: float,
    stat_date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """记录 API 调用用量（按天聚合）。"""
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        date = stat_date or today_str()
        conn.execute(
            """INSERT INTO usage_stats(stat_date, api_type, call_count, tokens_used, cost_estimate)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(stat_date, api_type) DO UPDATE SET
                 call_count=call_count+excluded.call_count,
                 tokens_used=tokens_used+excluded.tokens_used,
                 cost_estimate=cost_estimate+excluded.cost_estimate""",
            (date, api_type, call_count, tokens_used, cost_estimate),
        )
    finally:
        if own_conn:
            conn.commit()


def query_usage(start_date: Optional[str] = None, end_date: Optional[str] = None,
                conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own_conn = conn is None
    if own_conn:
        conn = get_db().__enter__()
    try:
        sql = "SELECT * FROM usage_stats WHERE 1=1"
        params: list[Any] = []
        if start_date:
            sql += " AND stat_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND stat_date <= ?"
            params.append(end_date)
        sql += " ORDER BY stat_date DESC, api_type"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.commit()
