# 文件路径：backend/screensight/infra/timeutil.py
# 文件作用：时间工具，统一 ISO8601 格式与本地时区处理
# 最后更新时间：2026-06-28-1949
"""时间工具模块。

时间存储统一使用带本地时区的 ISO8601 字符串（如 2026-06-28T19:49:00+08:00）。
北京时间为 +08:00 时区，所有报告/筛选基于本地时间。
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta, date
from typing import Optional

# 本地时区（北京时间 UTC+8）
LOCAL_TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    """当前时间的 ISO8601 字符串（带本地时区）。"""
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def now_dt() -> datetime:
    """当前时间的本地时区 datetime。"""
    return datetime.now(LOCAL_TZ)


def iso_to_dt(s: str) -> datetime:
    """ISO8601 字符串转 datetime（自动处理时区）。"""
    # 兼容无时区的字符串，按本地时区处理
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt


def today_str() -> str:
    """今天的日期字符串 YYYY-MM-DD。"""
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


def date_str(d: date) -> str:
    """date 转 YYYY-MM-DD。"""
    return d.strftime("%Y-%m-%d")


def parse_date(s: str) -> Optional[date]:
    """解析 YYYY-MM-DD 字符串。"""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def start_of_day(d: Optional[date] = None) -> str:
    """某天开始时间 ISO（00:00:00+08:00）。"""
    d = d or datetime.now(LOCAL_TZ).date()
    return datetime(d.year, d.month, d.day, tzinfo=LOCAL_TZ).isoformat(timespec="seconds")


def end_of_day(d: Optional[date] = None) -> str:
    """某天结束时间 ISO（次日 00:00:00+08:00，不含）。"""
    d = d or datetime.now(LOCAL_TZ).date()
    nxt = datetime(d.year, d.month, d.day, tzinfo=LOCAL_TZ) + timedelta(days=1)
    return nxt.isoformat(timespec="seconds")


def start_of_week(d: Optional[date] = None) -> str:
    """本周一开始时间（周一为一周起始）。"""
    d = d or datetime.now(LOCAL_TZ).date()
    monday = d - timedelta(days=d.weekday())
    return start_of_day(monday)


def start_of_month(d: Optional[date] = None) -> str:
    """本月开始时间。"""
    d = d or datetime.now(LOCAL_TZ).date()
    first = date(d.year, d.month, 1)
    return start_of_day(first)
