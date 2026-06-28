# 文件路径：backend/screensight/app.py
# 文件作用：FastAPI 应用入口，组装各服务与路由，启动后台调度
# 最后更新时间：2026-06-28-2015

"""FastAPI 应用入口。

组装配置、数据库、各服务与路由，启动截屏调度与定时任务。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import load_config, AppConfig, ensure_dirs, SCREENSHOT_DIR
from .db import init_db
from .services.recognize_service import RecognizeService
from .services.activity_service import ActivityService
from .services.storage_service import StorageService
from .services.capture_service import CaptureService, CaptureState
from .services.report_service import ReportService
from .services.search_service import SearchService

logger = logging.getLogger(__name__)


class AppContext:
    """应用上下文：统一持有各服务单例。"""

    def __init__(self, config: AppConfig):
        self.config = config
        # 初始化数据库与目录
        ensure_dirs()
        init_db()
        # 各服务
        self.recognize_service = RecognizeService(config)
        self.activity_service = ActivityService(config.settings)
        self.storage_service = StorageService(config.settings)
        self.report_service = ReportService(config)
        self.search_service = SearchService(config)
        # 截屏调度：识别回调串联识别+合并
        self.capture_service = CaptureService(
            config.settings,
            on_capture=self._on_capture,
        )
        self.scheduler: Optional["Scheduler"] = None

    def _on_capture(self, capture_id: int, screenshot, is_focused: bool) -> None:
        """焦点屏截图回调：识别 + 合并到活动时段。"""
        from .infra.timeutil import now_iso
        captured_at = now_iso()
        rid = self.recognize_service.recognize_and_store(capture_id, screenshot)
        if rid is not None:
            from .repositories import get_recognition
            rec = get_recognition(rid)
            if rec:
                self.activity_service.merge_recognition(
                    capture_id=capture_id,
                    captured_at=captured_at,
                    category=rec["category"],
                    sub_desc=rec["sub_desc"] or "",
                    object_name=rec["object_name"] or "",
                    is_low_confidence=bool(rec["is_low_confidence"]),
                )

    def start_background(self) -> None:
        """启动后台任务（截屏调度 + 定时报告）。"""
        from .scheduler import Scheduler
        self.capture_service.start()
        self.scheduler = Scheduler(self)
        self.scheduler.start()

    def stop_background(self) -> None:
        """停止后台任务。"""
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None
        self.capture_service.stop()


# 全局上下文（在 create_app 时赋值）
_ctx: Optional[AppContext] = None


def get_context() -> AppContext:
    """获取全局应用上下文。"""
    global _ctx
    if _ctx is None:
        _ctx = AppContext(load_config())
    return _ctx


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    """创建 FastAPI 应用。"""
    global _ctx
    if config is None:
        config = load_config()
    _ctx = AppContext(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动后台
        _ctx.start_background()
        logger.info("ScreenSight 后台服务已启动")
        yield
        _ctx.stop_background()
        logger.info("ScreenSight 后台服务已停止")

    app = FastAPI(title="ScreenSight", version="0.1.0", lifespan=lifespan)
    # CORS（本地前端访问）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 注册路由
    from .api import timeline, reports, search, settings as settings_api, stats, control
    app.include_router(timeline.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    app.include_router(control.router, prefix="/api")

    # 静态文件：截图访问
    from .config import SCREENSHOT_DIR
    if SCREENSHOT_DIR.exists():
        app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "state": _ctx.capture_service.state.value}

    return app
