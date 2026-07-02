# 文件路径：backend/screensight/services/activity_service.py
# 文件作用：活动合并服务，将连续同类识别结果合并为活动时段
# 最后更新时间：2026-06-28-2005

"""活动合并服务。

采用增量合并：每次新识别结果产生时，检查与当前活跃 segment 是否可合并。
可合并条件：一级类别相同 + 对象名相同 + 距上次截图间隔 < 容忍值。
"""
from __future__ import annotations

import logging
from typing import Optional

from ..config import Settings
from ..infra.timeutil import now_iso, iso_to_dt
from ..repositories import (
    get_open_segment, insert_segment, update_segment_append, close_segment,
    close_all_open_segments, query_segments,
)

logger = logging.getLogger(__name__)


class ActivityService:
    """活动合并服务。"""

    def __init__(self, settings: Settings):
        self._settings = settings
    def merge_recognition(
        self,
        capture_id: int,
        captured_at: str,
        category: str,
        sub_desc: str,
        object_name: str,
        is_low_confidence: bool = False,
    ) -> int:
        """将一条识别结果合并到活动时段。

        Returns:
            segment_id
        """
        # 查找可合并的未关闭时段
        seg = get_open_segment(category, object_name)
        if seg is not None:
            # 检查时间间隔是否在容忍范围内
            gap = (iso_to_dt(captured_at) - iso_to_dt(seg.end_time)).total_seconds()
            if gap <= self._settings.merge_gap_tolerance:
                # 可合并：追加
                update_segment_append(seg.id, captured_at, capture_id)
                return seg.id
            else:
                # 间隔过大：关闭旧时段，新建
                close_segment(seg.id)
        # 新建时段：预估结束时间为 start + 活跃截屏间隔
        # （代表这次活动至少持续到下次截屏前，使单条截图也有合理时长）
        from datetime import timedelta
        start_dt = iso_to_dt(captured_at)
        estimated_end = (start_dt + timedelta(seconds=self._settings.capture_interval_active)).isoformat()
        return insert_segment(
            start_time=captured_at,
            category=category,
            sub_desc=sub_desc,
            object_name=object_name,
            capture_ids=[capture_id],
            is_low_confidence=is_low_confidence,
            estimated_end=estimated_end,
        )

    def close_all(self) -> int:
        """关闭所有未关闭时段（暂停/锁屏时调用）。"""
        return close_all_open_segments()

    def get_segments(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        category: Optional[str] = None,
        object_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """查询活动时段。"""
        return query_segments(
            start=start, end=end, category=category, object_name=object_name,
            min_confidence=min_confidence, limit=limit,
        )
