# 文件路径：backend/screensight/services/storage_service.py
# 文件作用：存储与保留服务，截图存档、三级梯度保留、手动删除
# 最后更新时间：2026-06-28-2005

"""存储与保留服务。

负责：
1. 截图存档：焦点屏与其他屏分别压缩存储
2. 三级梯度保留：近期留原图 / 中期降质 / 远期仅留文本
3. 手动删除：删除时段及其关联截图文件
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from PIL import Image

from ..config import SCREENSHOT_DIR, Settings
from ..infra.screenshot import compress_for_archive, image_to_bytes
from ..infra.timeutil import LOCAL_TZ, now_dt
from ..repositories import delete_segment as repo_delete_segment

logger = logging.getLogger(__name__)


class StorageService:
    """存储与保留服务。"""

    def __init__(self, settings: Settings):
        self._settings = settings

    def save_archive(
        self,
        image: Image.Image,
        captured_at: str,
        monitor_index: int,
    ) -> str:
        """保存截图存档（低质量压缩）。

        Args:
            image: 原始截图
            captured_at: 截图时间 ISO8601
            monitor_index: 显示器序号
        Returns:
            存档文件相对路径
        """
        # 按日期分目录：screenshots/2026-06/28/20260628-200530_mon1.webp
        dt = datetime.fromisoformat(captured_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        rel_dir = f"{dt.strftime('%Y-%m')}/{dt.strftime('%d')}"
        abs_dir = SCREENSHOT_DIR / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{dt.strftime('%Y%m%d-%H%M%S')}_mon{monitor_index}.webp"
        rel_path = f"{rel_dir}/{filename}"
        abs_path = SCREENSHOT_DIR / rel_path
        # 压缩存档
        data = compress_for_archive(
            image,
            scale_percent=self._settings.archive_scale_near,
            quality=self._settings.archive_quality_near,
            fmt="WEBP",
        )
        with open(abs_path, "wb") as f:
            f.write(data)
        return rel_path

    def delete_segment_files(self, segment_id: int) -> int:
        """删除时段及其关联数据与截图文件。

        Returns:
            删除的截图文件数
        """
        paths = repo_delete_segment(segment_id)
        deleted = 0
        for rel_path in paths:
            abs_path = SCREENSHOT_DIR / rel_path
            try:
                if abs_path.exists():
                    abs_path.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning("删除截图文件失败 %s: %s", abs_path, e)
        return deleted

    def run_retention(self) -> dict:
        """执行三级梯度保留清理。

        Returns:
            统计信息 {downgraded, deleted}
        """
        from ..repositories import get_db
        now = now_dt()
        near_cutoff = now - timedelta(days=self._settings.retention_near_days)
        mid_cutoff = now - timedelta(days=self._settings.retention_mid_days)
        stats = {"downgraded": 0, "deleted": 0}
        # 中期降质：near_cutoff ~ mid_cutoff 之间的存档图降质
        stats["downgraded"] = self._downgrade_archives(near_cutoff, mid_cutoff)
        # 远期删除：mid_cutoff 之前的截图文件删除
        stats["deleted"] = self._delete_old_screenshots(mid_cutoff)
        return stats

    def _downgrade_archives(self, start_dt: datetime, end_dt: datetime) -> int:
        """将指定时间段的存档图降质压缩。"""
        count = 0
        # 遍历日期目录
        for d in self._iter_dates_between(start_dt, end_dt):
            rel_dir = f"{d.strftime('%Y-%m')}/{d.strftime('%d')}"
            abs_dir = SCREENSHOT_DIR / rel_dir
            if not abs_dir.exists():
                continue
            for f in abs_dir.glob("*.webp"):
                try:
                    img = Image.open(f)
                    data = compress_for_archive(
                        img,
                        scale_percent=self._settings.archive_scale_mid,
                        quality=self._settings.archive_quality_mid,
                        fmt="WEBP",
                    )
                    with open(f, "wb") as fp:
                        fp.write(data)
                    count += 1
                except Exception as e:
                    logger.warning("降质失败 %s: %s", f, e)
        return count

    def _delete_old_screenshots(self, cutoff_dt: datetime) -> int:
        """删除 cutoff 之前的截图文件（保留识别记录）。"""
        count = 0
        for d in self._iter_dates_before(cutoff_dt):
            rel_dir = f"{d.strftime('%Y-%m')}/{d.strftime('%d')}"
            abs_dir = SCREENSHOT_DIR / rel_dir
            if not abs_dir.exists():
                continue
            for f in abs_dir.glob("*.webp"):
                try:
                    f.unlink()
                    count += 1
                except Exception as e:
                    logger.warning("删除截图失败 %s: %s", f, e)
            # 空目录清理
            try:
                if not any(abs_dir.iterdir()):
                    abs_dir.rmdir()
            except Exception:
                pass
        return count

    def _iter_dates_between(self, start_dt: datetime, end_dt: datetime):
        """枚举两个日期之间的所有日期（不含 end）。"""
        d = start_dt.date()
        end = end_dt.date()
        while d < end:
            yield d
            d += timedelta(days=1)

    def _iter_dates_before(self, cutoff_dt: datetime):
        """枚举 cutoff 之前的日期目录（扫描存在的目录）。"""
        if not SCREENSHOT_DIR.exists():
            return
        cutoff_date = cutoff_dt.date()
        for year_month_dir in SCREENSHOT_DIR.iterdir():
            if not year_month_dir.is_dir():
                continue
            for day_dir in year_month_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                try:
                    d = datetime.strptime(
                        f"{year_month_dir.name}-{day_dir.name}", "%Y-%m-%d"
                    ).date()
                except ValueError:
                    continue
                if d < cutoff_date:
                    yield d
