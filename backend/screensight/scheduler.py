# 文件路径：backend/screensight/scheduler.py
# 文件作用：定时任务调度，自动生成报告与执行保留清理
# 最后更新时间：2026-06-28-2015

"""定时任务调度。

使用 APScheduler 调度：
- 每小时末生成小时报
- 每日 23:30 生成日报
- 每周一 08:00 生成周报
- 每月 1 号 08:00 生成月报
- 每日 03:00 执行保留清理
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from .app import AppContext

logger = logging.getLogger(__name__)


class Scheduler:
    """定时任务调度器。"""

    def __init__(self, ctx: "AppContext"):
        self._ctx = ctx
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        """启动定时任务。"""
        ctx = self._ctx
        # 每小时末生成小时报（每小时第 59 分）
        self._scheduler.add_job(
            self._safe_job("hourly"), CronTrigger(minute=59),
            id="hourly_report", replace_existing=True,
        )
        # 每日 23:30 生成日报
        self._scheduler.add_job(
            self._safe_job("daily"), CronTrigger(hour=23, minute=30),
            id="daily_report", replace_existing=True,
        )
        # 每周一 08:00 生成周报
        self._scheduler.add_job(
            self._safe_job("weekly"), CronTrigger(day_of_week="mon", hour=8),
            id="weekly_report", replace_existing=True,
        )
        # 每月 1 号 08:00 生成月报
        self._scheduler.add_job(
            self._safe_job("monthly"), CronTrigger(day=1, hour=8),
            id="monthly_report", replace_existing=True,
        )
        # 每日 03:00 执行保留清理
        self._scheduler.add_job(
            self._retention_job, CronTrigger(hour=3),
            id="retention", replace_existing=True,
        )
        self._scheduler.start()
        logger.info("定时任务调度器已启动")

    def stop(self) -> None:
        """停止定时任务。"""
        self._scheduler.shutdown(wait=False)
        logger.info("定时任务调度器已停止")

    def _safe_job(self, report_type: str):
        """包装报告生成任务，捕获异常避免调度器崩溃。"""
        def job():
            try:
                logger.info("自动生成 %s 报告", report_type)
                report = self._ctx.report_service.generate_report(report_type, use_llm=True)
                logger.info("%s 报告生成完成，总时长 %s 秒",
                            report_type, report["stats"]["total_seconds"])
            except Exception as e:
                logger.error("生成 %s 报告失败: %s", report_type, e)
        return job

    def _retention_job(self) -> None:
        """保留清理任务。"""
        try:
            stats = self._ctx.storage_service.run_retention()
            logger.info("保留清理完成: 降质 %s 张, 删除 %s 张", stats["downgraded"], stats["deleted"])
        except Exception as e:
            logger.error("保留清理失败: %s", e)
