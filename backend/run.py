# 文件路径：backend/run.py
# 文件作用：ScreenSight 后端启动入口
# 最后更新时间：2026-06-28-2015
"""ScreenSight 后端启动入口。

用法：python run.py
启动 FastAPI 服务（含截屏调度与定时任务）。
"""
from __future__ import annotations

import logging
import sys
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
    logging.info("启动 ScreenSight 后端服务 http://%s:%s", config.host, config.port)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
