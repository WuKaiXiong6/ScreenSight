# 文件路径：backend/screensight/api/control.py
# 文件作用：控制 API，暂停/恢复记录、查询状态
# 最后更新时间：2026-06-28-2015
"""控制 API。"""
from __future__ import annotations
from fastapi import APIRouter

from ..app import get_context

router = APIRouter(tags=["control"])


@router.get("/control/status")
async def get_status():
    """获取当前截屏状态。"""
    ctx = get_context()
    return {"state": ctx.capture_service.state.value}


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
