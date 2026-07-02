# 文件路径：backend/screensight/api/stats.py
# 文件作用：费用统计 API
# 最后更新时间：2026-07-02-1209
"""费用统计 API。"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query

from ..app import get_context
from ..repositories import (
    query_usage, query_usage_hourly, query_usage_trend, query_usage_breakdown,
)
from ..infra.timeutil import today_str

router = APIRouter(tags=["stats"])


@router.get("/stats/usage")
async def get_usage(
    days: int = Query(30, description="最近N天"),
):
    """获取 API 调用用量统计（明细，按天与类型）。"""
    from datetime import timedelta
    from ..infra.timeutil import now_dt
    end = today_str()
    start_date = (now_dt() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = query_usage(start_date=start_date, end_date=end)
    # 按天与类型聚合展示
    return {"start": start_date, "end": end, "records": rows}


@router.get("/stats/usage/trend")
async def get_usage_trend(
    days: int = Query(30, description="最近N天"),
):
    """获取按天费用趋势（每天一行：date/total_calls/total_tokens/total_cost）。"""
    from datetime import timedelta
    from ..infra.timeutil import now_dt
    end = today_str()
    start_date = (now_dt() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = query_usage_trend(start_date=start_date, end_date=end)
    return {"start": start_date, "end": end, "trend": rows}


@router.get("/stats/usage/hourly")
async def get_usage_hourly(
    days: int = Query(3, description="最近N天的小时级数据"),
):
    """获取小时级用量（用于单小时成本与细粒度趋势）。"""
    from datetime import timedelta
    from ..infra.timeutil import now_dt
    start = (now_dt() - timedelta(days=days)).strftime("%Y-%m-%d %H:00")
    end = now_dt().strftime("%Y-%m-%d %H:00")
    rows = query_usage_hourly(start_hour=start, end_hour=end)
    return {"start": start, "end": end, "records": rows}


@router.get("/stats/usage/breakdown")
async def get_usage_breakdown(
    days: int = Query(30, description="最近N天"),
):
    """获取按 api_type 的费用占比（vlm/llm/embedding）。"""
    from datetime import timedelta
    from ..infra.timeutil import now_dt
    end = today_str()
    start_date = (now_dt() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = query_usage_breakdown(start_date=start_date, end_date=end)
    return {"start": start_date, "end": end, "breakdown": rows}
