# 文件路径：backend/screensight/api/settings.py
# 文件作用：设置 API，读取与更新运行参数
# 最后更新时间：2026-06-28-2015
"""设置 API。"""
from __future__ import annotations
from dataclasses import asdict
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..app import get_context
from ..config import Settings
from ..repositories import get_all_settings, set_setting

router = APIRouter(tags=["settings"])

# 可通过界面修改的参数键
EDITABLE_KEYS = {
    "capture_interval_active", "capture_interval_idle", "idle_threshold",
    "low_confidence_threshold", "archive_quality_near", "archive_scale_near",
    "retention_near_days", "retention_mid_days", "merge_gap_tolerance", "rag_top_k",
}


@router.get("/settings")
async def get_settings():
    """获取当前设置。"""
    ctx = get_context()
    # 合并数据库覆盖值
    stored = get_all_settings()
    settings = asdict(ctx.config.settings)
    for k in EDITABLE_KEYS:
        if k in stored:
            val = stored[k]
            # 类型转换
            field_type = type(getattr(ctx.config.settings, k))
            try:
                settings[k] = field_type(val)
            except (TypeError, ValueError):
                pass
    return settings


class UpdateSettingsRequest(BaseModel):
    capture_interval_active: Optional[int] = None
    capture_interval_idle: Optional[int] = None
    idle_threshold: Optional[int] = None
    low_confidence_threshold: Optional[float] = None
    archive_quality_near: Optional[int] = None
    archive_scale_near: Optional[int] = None
    retention_near_days: Optional[int] = None
    retention_mid_days: Optional[int] = None
    merge_gap_tolerance: Optional[int] = None
    rag_top_k: Optional[int] = None


@router.put("/settings")
async def update_settings(req: UpdateSettingsRequest):
    """更新设置。"""
    ctx = get_context()
    updated = []
    for k, v in req.model_dump(exclude_none=True).items():
        if k in EDITABLE_KEYS:
            set_setting(k, str(v))
            # 同步到运行时
            field_type = type(getattr(ctx.config.settings, k))
            try:
                setattr(ctx.config.settings, k, field_type(v))
                updated.append(k)
            except (TypeError, ValueError):
                pass
    return {"updated": updated}
