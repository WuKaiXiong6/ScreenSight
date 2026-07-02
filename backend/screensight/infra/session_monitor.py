# 文件路径：backend/screensight/infra/session_monitor.py
# 文件作用：Windows 锁屏/会话状态检测，监听锁屏与解锁事件
# 最后更新时间：2026-06-28-1949

"""锁屏/会话状态检测。

Windows 平台通过监听 WM_WTSSESSION_CHANGE 消息捕获锁屏/解锁事件。
由于 Python 直接接收窗口消息需要消息循环，这里采用轮询前台窗口的备用方案：
检测前台窗口是否为 LogonUI（锁屏界面）或 Winlogon 进程。

更精确的事件监听方案（WTRegisterSessionNotification）需要隐藏窗口 + 消息循环，
留作后续优化，当前轮询方案足以满足"锁屏时停止截屏"需求。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 锁屏界面相关进程名（小写）
_LOCK_SCREEN_PROCESSES = {"logonui.exe", "logonui", "winlogon.exe"}


def _get_foreground_process_name() -> Optional[str]:
    """获取前台窗口所属进程名。"""
    try:
        import win32gui
        import win32process
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        # 获取窗口所属进程 ID
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        # 用 wmi 或 ctypes 获取进程名，避免引入 psutil
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            # QueryFullProcessImageNameW
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                # 取文件名部分
                name = buf.value.rsplit("\\", 1)[-1]
                return name.lower()
            return None
        finally:
            kernel32.CloseHandle(h)
    except Exception as e:
        logger.debug("获取前台进程名失败: %s", e)
        return None


def is_screen_locked() -> bool:
    """检测当前是否处于锁屏状态。

    通过检测前台窗口是否为 LogonUI 判定。
    """
    name = _get_foreground_process_name()
    if name and name in _LOCK_SCREEN_PROCESSES:
        return True
    # 备用：检测 OpenInputDesktop 是否可访问（锁屏时输入桌面切换）
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # GetForegroundWindow 返回 0 也可能表示锁屏
        if not user32.GetForegroundWindow():
            # 进一步确认：OpenInputDesktop 在锁屏时返回的桌面与默认不同
            # 简化：前台窗口为 None 且能拿到 LogonUI 才判定锁屏
            return False
    except Exception:
        pass
    return False


class SessionMonitor:
    """会话状态监控器（轮询方式）。

    定期检测锁屏状态，状态变化时触发回调。
    """

    def __init__(
        self,
        poll_interval: float = 5.0,
        on_lock: Optional[Callable[[], None]] = None,
        on_unlock: Optional[Callable[[], None]] = None,
    ):
        self._poll_interval = poll_interval
        self._on_lock = on_lock
        self._on_unlock = on_unlock
        self._locked = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_locked(self) -> bool:
        return self._locked

    def start(self) -> None:
        """启动轮询检测。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("锁屏状态监控已启动")

    def stop(self) -> None:
        """停止轮询检测。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval * 2)
            self._thread = None

    def _poll_loop(self) -> None:
        """轮询锁屏状态。"""
        while not self._stop_event.is_set():
            try:
                locked = is_screen_locked()
                if locked and not self._locked:
                    self._locked = True
                    logger.info("检测到锁屏")
                    if self._on_lock:
                        self._on_lock()
                elif not locked and self._locked:
                    self._locked = False
                    logger.info("检测到解锁")
                    if self._on_unlock:
                        self._on_unlock()
            except Exception as e:
                logger.error("锁屏检测异常: %s", e)
            self._stop_event.wait(self._poll_interval)


# 全局单例
_global_session: Optional[SessionMonitor] = None
_global_lock = threading.Lock()


def get_session_monitor() -> SessionMonitor:
    """获取全局 SessionMonitor 单例。"""
    global _global_session
    if _global_session is None:
        with _global_lock:
            if _global_session is None:
                _global_session = SessionMonitor()
    return _global_session
