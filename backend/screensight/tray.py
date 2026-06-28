# 文件路径：backend/screensight/tray.py
# 文件作用：系统托盘，常驻后台，提供打开界面/暂停恢复/退出功能
# 最后更新时间：2026-06-28-2040

"""系统托盘。

使用 pystray 实现系统托盘图标与菜单：
- 打开界面：在默认浏览器打开本地 Web 界面
- 暂停/恢复：切换记录状态
- 退出：停止后台服务并退出

托盘运行在独立线程，与 FastAPI 通过共享的 AppContext 通信。
"""
from __future__ import annotations

import logging
import threading
import webbrowser
from typing import Optional

from PIL import Image, ImageDraw

from .app import get_context

logger = logging.getLogger(__name__)


def _create_icon_image() -> Image.Image:
    """生成托盘图标（简单的时钟样式）。"""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 外圈
    draw.ellipse([6, 6, 58, 58], outline=(22, 104, 220, 255), width=4)
    # 时针/分针
    draw.line([32, 32, 32, 14], fill=(22, 104, 220, 255), width=3)
    draw.line([32, 32, 46, 32], fill=(22, 104, 220, 255), width=3)
    return img


class TrayApp:
    """系统托盘应用。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self._host = host
        self._port = port
        self._tray = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动托盘（独立线程）。"""
        import pystray
        from .services.capture_service import CaptureState

        def on_open(icon, item):
            webbrowser.open(f"http://{self._host}:{self._port}")

        def on_pause(icon, item):
            ctx = get_context()
            if ctx.capture_service.state != CaptureState.PAUSED:
                ctx.capture_service.pause()
                ctx.activity_service.close_all()
            self._update_icon(icon)

        def on_resume(icon, item):
            ctx = get_context()
            ctx.capture_service.resume()
            self._update_icon(icon)

        def on_quit(icon, item):
            icon.stop()

        def build_menu():
            ctx = get_context()
            is_paused = ctx.capture_service.state == CaptureState.PAUSED
            return pystray.Menu(
                pystray.MenuItem("打开界面", on_open, default=True),
                pystray.MenuItem(
                    "恢复记录" if is_paused else "暂停记录",
                    on_resume if is_paused else on_pause,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", on_quit),
            )

        self._build_menu = build_menu

        self._tray = pystray.Icon(
            "ScreenSight",
            _create_icon_image(),
            "ScreenSight",
            menu=build_menu(),
        )
        self._thread = threading.Thread(target=self._tray.run, daemon=True)
        self._thread.start()
        logger.info("系统托盘已启动")

    def _update_icon(self, icon) -> None:
        """状态变化后刷新菜单。"""
        icon.menu = self._build_menu()
        icon.update_menu()

    def stop(self) -> None:
        """停止托盘。"""
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
