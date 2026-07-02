# 文件路径：backend/screensight/api/stats.py
# 文件作用：费用统计 API
# 最后更新时间：2026-06-28-2015
"""费用统计 API。"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query

from ..app import get_context
from ..repositories import query_usage
from ..infra.timeutil import today_str

router = APIRouter(tags=["stats"])


@router.get("/stats/usage")
async def get_usage(
    days: int = Query(30, description="最近N天"),
):
    """获取 API 调用用量统计。"""
    from datetime import timedelta
    from ..infra.timeutil import now_dt
    end = today_str()
    start_date = (now_dt() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = query_usage(start_date=start_date, end_date=end)
    # 按天与类型聚合展示
    return {"start": start_date, "end": end, "records": rows}
