# 文件路径：backend/run.py
# 文件作用：ScreenSight 后端启动入口（含系统托盘）
# 最后更新时间：2026-06-28-2040
"""ScreenSight 后端启动入口。

启动 FastAPI 服务（含截屏调度与定时任务）+ 系统托盘，
并自动在浏览器打开界面。

用法：python run.py
"""
from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from pathlib import Path

# 将 backend 目录加入 sys.path，使 screensight 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from screensight.app import create_app
from screensight.config import load_config


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = load_config()
    app = create_app(config)

    # 启动系统托盘
    try:
        from screensight.tray import TrayApp
        tray = TrayApp(config.host, config.port)
        tray.start()
    except Exception as e:
        logging.warning("系统托盘启动失败（不影响核心功能）: %s", e)
        tray = None

    # 延迟打开浏览器（等服务就绪）
    def open_browser():
        import time
        time.sleep(2)
        webbrowser.open(f"http://{config.host}:{config.port}")
    threading.Thread(target=open_browser, daemon=True).start()

    logging.info("启动 ScreenSight 后端服务 http://%s:%s", config.host, config.port)
    try:
        uvicorn.run(app, host=config.host, port=config.port, log_level="warning")
    finally:
        if tray:
            tray.stop()


if __name__ == "__main__":
    main()
