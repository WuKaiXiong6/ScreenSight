# 文件路径：backend/screensight/api/timeline.py
# 文件作用：时间线 API，提供活动时段查询与删除
# 最后更新时间：2026-06-28-2015
"""时间线 API。"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..app import get_context
from ..infra.timeutil import LOCAL_TZ, start_of_day, end_of_day, iso_to_dt, parse_date

router = APIRouter(tags=["timeline"])


@router.get("/timeline")
async def get_timeline(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，默认今天"),
    period: str = Query("day", description="day/week/month"),
):
    """获取时间线活动时段。"""
    ctx = get_context()
    if date:
        d = parse_date(date)
        if d is None:
            raise HTTPException(400, "日期格式应为 YYYY-MM-DD")
    else:
        d = datetime.now(LOCAL_TZ).date()
    # 计算时间范围
    if period == "day":
        start = start_of_day(d)
        end = end_of_day(d)
    elif period == "week":
        monday = d - timedelta(days=d.weekday())
        start = start_of_day(monday)
        end = end_of_day(monday + timedelta(days=6))
    elif period == "month":
        start = start_of_day(datetime(d.year, d.month, 1).date())
        if d.month == 12:
            end_d = datetime(d.year + 1, 1, 1).date()
        else:
            end_d = datetime(d.year, d.month + 1, 1).date()
        end = end_of_day(end_d - timedelta(days=1))
    else:
        raise HTTPException(400, "period 应为 day/week/month")
    segments = ctx.activity_service.get_segments(start=start, end=end, limit=5000)
    return {"date": date, "period": period, "start": start, "end": end, "segments": segments}


@router.get("/timeline/segment/{segment_id}")
async def get_segment_detail(segment_id: int):
    """获取时段详情（含截图列表）。"""
    from ..repositories import get_db, get_capture
    import json
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM activity_segments WHERE id=?", (segment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "时段不存在")
        seg = dict(row)
        seg["capture_ids"] = json.loads(seg["capture_ids"])
        # 取截图详情
        captures = []
        for cid in seg["capture_ids"]:
            c = get_capture(cid)
            if c:
                captures.append(c)
        seg["captures"] = captures
        return seg


@router.delete("/timeline/segment/{segment_id}")
async def delete_segment(segment_id: int):
    """删除时段（隐私擦除）。"""
    ctx = get_context()
    deleted = ctx.storage_service.delete_segment_files(segment_id)
    return {"deleted_files": deleted}
