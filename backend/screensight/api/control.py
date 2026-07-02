# 文件路径：backend/screensight/api/control.py
# 文件作用：控制 API，暂停/恢复记录、查询状态
# 最后更新时间：2026-07-02-1209
"""控制 API。"""
from __future__ import annotations
from fastapi import APIRouter

from ..app import get_context
from ..repositories import get_recent_activity

router = APIRouter(tags=["control"])


@router.get("/control/status")
async def get_status():
    """获取当前截屏状态及最近活动信息。

    返回：
      state: 截屏状态机值（ACTIVE/IDLE/LOCKED/PAUSED）
      last_capture_at: 最近一次截屏时间（ISO），无则 null
      last_recognition_at: 最近一次识别成功时间（ISO），无则 null
      last_data_date: 最近有活动段数据的日期（YYYY-MM-DD），无则 null
      today_cost: 今日预估费用合计
      recent_error_count: 最近 30 分钟内失败截屏数
    """
    ctx = get_context()
    recent = get_recent_activity()
    return {"state": ctx.capture_service.state.value, **recent}


@router.post("/control/pause")
async def pause():
    """暂停记录。"""
    ctx = get_context()
    ctx.capture_service.pause()
    # 暂停时关闭所有未关闭时段
    ctx.activity_service.close_all()
    return {"state": ctx.capture_service.state.value}


@router.post("/control/resume")
async def resume():
    """恢复记录。"""
    ctx = get_context()
    ctx.capture_service.resume()
    return {"state": ctx.capture_service.state.value}
