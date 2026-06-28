# 文件路径：backend/screensight/infra/activity_monitor.py
# 文件作用：键鼠活动检测，记录最后活动时间，判定用户是否在线/空闲
# 最后更新时间：2026-06-28-1949

"""键鼠活动检测。

使用 pynput 监听键盘/鼠标事件，记录最后活动时间戳。
判断用户是否在线完全依据键鼠活动（不依赖画面变化）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ActivityMonitor:
    """键鼠活动监控器。

    通过 pynput 监听全局键鼠事件，维护"最后活动时间"。
    线程安全，可被多线程读取 last_activity_time。
    """

    def __init__(self):
        self._last_activity: float = time.time()
        self._lock = threading.Lock()
        self._kb_listener = None
        self._mouse_listener = None
        self._started = False

    @property
    def last_activity_time(self) -> float:
        with self._lock:
            return self._last_activity

    def _on_activity(self, *args, **kwargs) -> None:
        """键鼠事件回调：更新最后活动时间。"""
        with self._lock:
            self._last_activity = time.time()

    def start(self) -> None:
        """启动键鼠监听。"""
        if self._started:
            return
        try:
            from pynput import keyboard, mouse
            # 鼠标移动事件较频繁，仅监听点击与滚轮以减少开销
            self._kb_listener = keyboard.Listener(
                on_press=self._on_activity, on_release=self._on_activity,
            )
            self._mouse_listener = mouse.Listener(
                on_click=self._on_activity,
                on_scroll=self._on_activity,
            )
            self._kb_listener.start()
            self._mouse_listener.start()
            self._started = True
            logger.info("键鼠活动监听已启动")
        except Exception as e:
            logger.error("启动键鼠监听失败: %s", e)
            # 非致命：降级为始终认为活跃
            self._last_activity = time.time()

    def stop(self) -> None:
        """停止键鼠监听。"""
        if self._kb_listener is not None:
            self._kb_listener.stop()
            self._kb_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        self._started = False

    def seconds_since_last_activity(self) -> float:
        """距上次键鼠活动的秒数。"""
        return time.time() - self.last_activity_time

    def is_idle(self, idle_threshold: float) -> bool:
        """是否空闲（距上次活动超过阈值）。"""
        return self.seconds_since_last_activity() > idle_threshold


# 全局单例
_global_monitor: Optional[ActivityMonitor] = None
_global_lock = threading.Lock()


def get_activity_monitor() -> ActivityMonitor:
    """获取全局 ActivityMonitor 单例。"""
    global _global_monitor
    if _global_monitor is None:
        with _global_lock:
            if _global_monitor is None:
                _global_monitor = ActivityMonitor()
    return _global_monitor
