# 文件路径：backend/screensight/services/capture_service.py
# 文件作用：截屏调度服务，状态机驱动截屏循环（ACTIVE/IDLE/LOCKED/PAUSED）
# 最后更新时间：2026-06-28-2005

"""截屏调度服务。

状态机：
  ACTIVE  — 键鼠活动正常，每 30s 截屏
  IDLE    — 键鼠无活动超阈值，每 5min 截屏（检测恢复）
  LOCKED  — 锁屏，完全停止截屏
  PAUSED  — 用户手动暂停，完全停止截屏

状态转换：
  ACTIVE → IDLE: 键鼠无活动 > idle_threshold
  IDLE → ACTIVE: 键鼠恢复活动
  * → LOCKED: 检测到锁屏
  LOCKED → ACTIVE: 解锁（恢复活跃）
  * → PAUSED: 用户手动暂停
  PAUSED → ACTIVE: 用户恢复
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

from ..config import Settings
from ..infra.activity_monitor import get_activity_monitor
from ..infra.screenshot import (
    capture_all_monitors, capture_focused_monitor, ScreenshotResult,
)
from ..infra.session_monitor import get_session_monitor, SessionMonitor
from ..infra.timeutil import now_iso
from ..repositories import insert_capture

logger = logging.getLogger(__name__)


class CaptureState(str, Enum):
    """截屏状态。"""
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    LOCKED = "LOCKED"
    PAUSED = "PAUSED"


class CaptureService:
    """截屏调度服务。"""

    def __init__(
        self,
        settings: Settings,
        on_capture: Optional[Callable[[int, ScreenshotResult, bool], None]] = None,
    ):
        """
        Args:
            settings: 运行参数
            on_capture: 截图回调 (capture_id, screenshot, is_focused)
                        由调用方触发识别与合并
        """
        self._settings = settings
        self._on_capture = on_capture
        self._state = CaptureState.ACTIVE
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._activity_monitor = get_activity_monitor()
        self._session_monitor = get_session_monitor()
        self._last_capture_time: float = 0.0

    @property
    def state(self) -> CaptureState:
        with self._state_lock:
            return self._state

    def _set_state(self, new_state: CaptureState) -> None:
        with self._state_lock:
            old = self._state
            self._state = new_state
        if old != new_state:
            logger.info("状态转换: %s → %s", old.value, new_state.value)

    def start(self) -> None:
        """启动截屏循环。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        # 启动活动检测与锁屏检测
        self._activity_monitor.start()
        self._session_monitor._on_lock = self._on_lock
        self._session_monitor._on_unlock = self._on_unlock
        self._session_monitor.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("截屏调度服务已启动")

    def stop(self) -> None:
        """停止截屏循环。"""
        self._stop_event.set()
        self._session_monitor.stop()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("截屏调度服务已停止")

    def pause(self) -> None:
        """手动暂停。"""
        self._set_state(CaptureState.PAUSED)
        logger.info("用户手动暂停")

    def resume(self) -> None:
        """手动恢复。"""
        if self._state == CaptureState.PAUSED:
            self._set_state(CaptureState.ACTIVE)
            self._activity_monitor._last_activity = time.time()
            logger.info("用户手动恢复")

    def _on_lock(self) -> None:
        """锁屏回调。"""
        if self._state != CaptureState.PAUSED:
            self._set_state(CaptureState.LOCKED)

    def _on_unlock(self) -> None:
        """解锁回调。"""
        if self._state == CaptureState.LOCKED:
            self._set_state(CaptureState.ACTIVE)
            self._activity_monitor._last_activity = time.time()

    def _get_current_interval(self) -> float:
        """根据当前状态决定截屏间隔。"""
        if self._state == CaptureState.ACTIVE:
            return self._settings.capture_interval_active
        if self._state == CaptureState.IDLE:
            return self._settings.capture_interval_idle
        # LOCKED / PAUSED 不截屏，但需要轮询检测状态变化
        return 5.0

    def _check_state_transitions(self) -> None:
        """检查并执行状态转换。"""
        if self._state == CaptureState.PAUSED:
            return  # 手动暂停态，等待用户恢复
        if self._state == CaptureState.LOCKED:
            return  # 锁屏态，由 _on_unlock 处理
        if self._state == CaptureState.ACTIVE:
            # 检查是否进入空闲
            if self._activity_monitor.is_idle(self._settings.idle_threshold):
                self._set_state(CaptureState.IDLE)
        elif self._state == CaptureState.IDLE:
            # 检查是否恢复活跃
            if not self._activity_monitor.is_idle(self._settings.idle_threshold):
                self._set_state(CaptureState.ACTIVE)

    def _loop(self) -> None:
        """截屏主循环。"""
        while not self._stop_event.is_set():
            self._check_state_transitions()
            # 仅在 ACTIVE 或 IDLE 状态截屏
            if self._state in (CaptureState.ACTIVE, CaptureState.IDLE):
                interval = self._get_current_interval()
                if time.time() - self._last_capture_time >= interval:
                    try:
                        self._do_capture()
                        self._last_capture_time = time.time()
                    except Exception as e:
                        logger.error("截屏失败: %s", e)
                        self._last_capture_time = time.time()
            # 等待下一轮（短间隔轮询状态变化）
            self._stop_event.wait(1.0)

    def _do_capture(self) -> None:
        """执行一次截屏：截所有屏，焦点屏存高清送识别，其余屏存档。"""
        captured_at = now_iso()
        results = capture_all_monitors()
        if not results:
            return
        for result in results:
            # 所有屏都存档
            from ..services.storage_service import StorageService
            storage = StorageService(self._settings)
            try:
                archive_path = storage.save_archive(
                    result.image, captured_at, result.monitor.index
                )
            except Exception as e:
                logger.error("存档失败: %s", e)
                archive_path = None
            # 写入截图记录
            capture_id = insert_capture(
                captured_at=captured_at,
                monitor_index=result.monitor.index,
                is_focused=result.is_focused,
                width=result.image.width,
                height=result.image.height,
                archive_path=archive_path,
                recognition_status="success" if result.is_focused else "skipped",
            )
            # 焦点屏触发识别回调
            if result.is_focused and self._on_capture is not None:
                try:
                    self._on_capture(capture_id, result, True)
                except Exception as e:
                    logger.error("识别回调失败: %s", e)
                    update_capture_recognition_safe(capture_id, "failed")


def update_capture_recognition_safe(capture_id: int, status: str) -> None:
    """安全更新截图状态（忽略错误）。"""
    try:
        from ..repositories import update_capture_recognition
        update_capture_recognition(capture_id, status)
    except Exception:
        pass
