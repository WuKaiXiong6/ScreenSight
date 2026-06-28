# 文件路径：backend/screensight/infra/screenshot.py
# 文件作用：屏幕截图引擎封装，支持多显示器与焦点屏判定
# 最后更新时间：2026-06-28-1949

"""截图引擎。

基于 mss 实现多显示器截图，基于 win32gui 判定焦点屏（活动窗口所在显示器）。
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class MonitorInfo:
    """显示器信息。"""
    index: int          # mss 显示器序号（1 为主屏）
    left: int
    top: int
    width: int
    height: int
    is_primary: bool


@dataclass
class ScreenshotResult:
    """截图结果。"""
    monitor: MonitorInfo
    image: Image.Image  # PIL Image
    is_focused: bool


def list_monitors() -> list[MonitorInfo]:
    """列出所有显示器。"""
    import mss
    monitors: list[MonitorInfo] = []
    with mss.MSS() as sct:
        # sct.monitors[0] 是所有屏的合并区域，[1:] 才是各物理屏
        for i, m in enumerate(sct.monitors[1:], start=1):
            monitors.append(MonitorInfo(
                index=i,
                left=m["left"],
                top=m["top"],
                width=m["width"],
                height=m["height"],
                is_primary=(i == 1),
            ))
    return monitors


def get_focused_monitor_index() -> int:
    """获取焦点屏（前台窗口所在显示器）序号。

    Windows 平台用 win32gui + win32api 判定。
    返回 mss 显示器序号（1-based），失败回退到主屏 1。
    """
    try:
        import win32gui
        import win32api  # noqa: F401
        import win32con
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return 1
        # MonitorFromWindow 获取窗口所在显示器句柄
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        # 获取该显示器信息
        info = win32api.GetMonitorInfo(monitor)
        monitor_rect = info["Monitor"]
        # 匹配到 mss 显示器序号
        monitors = list_monitors()
        for m in monitors:
            if (m.left == monitor_rect[0] and m.top == monitor_rect[1]
                    and m.width == monitor_rect[2] - monitor_rect[0]
                    and m.height == monitor_rect[3] - monitor_rect[1]):
                return m.index
        return 1
    except Exception as e:
        logger.debug("焦点屏判定失败，回退主屏: %s", e)
        return 1


def capture_monitor(monitor_index: int) -> Optional[ScreenshotResult]:
    """截取指定显示器。

    Args:
        monitor_index: mss 显示器序号（1-based）
    Returns:
        ScreenshotResult 或 None（失败时）
    """
    import mss
    monitors = list_monitors()
    if monitor_index < 1 or monitor_index > len(monitors):
        logger.warning("无效的显示器序号: %s", monitor_index)
        return None
    target = monitors[monitor_index - 1]
    with mss.MSS() as sct:
        # mss 显示器序号对应 monitors 列表索引（含合并区，所以是 monitor_index）
        raw = sct.grab({
            "left": target.left,
            "top": target.top,
            "width": target.width,
            "height": target.height,
            "mon": monitor_index,
        })
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    focused_idx = get_focused_monitor_index()
    return ScreenshotResult(
        monitor=target,
        image=img,
        is_focused=(monitor_index == focused_idx),
    )


def capture_all_monitors() -> list[ScreenshotResult]:
    """截取所有显示器。"""
    monitors = list_monitors()
    focused_idx = get_focused_monitor_index()
    results: list[ScreenshotResult] = []
    import mss
    with mss.MSS() as sct:
        for m in monitors:
            raw = sct.grab({
                "left": m.left, "top": m.top,
                "width": m.width, "height": m.height,
                "mon": m.index,
            })
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            results.append(ScreenshotResult(
                monitor=m, image=img, is_focused=(m.index == focused_idx),
            ))
    return results


def capture_focused_monitor() -> Optional[ScreenshotResult]:
    """只截取焦点屏。"""
    idx = get_focused_monitor_index()
    return capture_monitor(idx)


def image_to_bytes(img: Image.Image, fmt: str = "PNG", quality: int = 95) -> bytes:
    """将 PIL Image 转为字节。

    Args:
        img: PIL 图像
        fmt: 格式 PNG/WEBP/JPEG
        quality: 质量（JPEG/WEBP 有效）
    """
    buf = io.BytesIO()
    kwargs: dict = {}
    if fmt.upper() in ("JPEG", "WEBP"):
        kwargs["quality"] = quality
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def compress_for_archive(
    img: Image.Image,
    scale_percent: int = 50,
    quality: int = 70,
    fmt: str = "WEBP",
) -> bytes:
    """将截图压缩为存档格式（低质量 + 缩放，节省磁盘）。

    Args:
        img: 原始截图
        scale_percent: 缩放百分比（50 表示缩小到 50%）
        quality: 压缩质量
        fmt: 存档格式
    """
    if scale_percent < 100:
        new_w = max(1, int(img.width * scale_percent / 100))
        new_h = max(1, int(img.height * scale_percent / 100))
        img = img.resize((new_w, new_h), Image.LANCZOS)
    return image_to_bytes(img, fmt=fmt, quality=quality)
