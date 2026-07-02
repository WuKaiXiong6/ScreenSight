# 文件路径：backend/tests/test_infra.py
# 文件作用：基础设施层单元测试（配置/数据库/截图/活动检测/锁屏检测）
# 最后更新时间：2026-06-28-1949

"""基础设施层测试。"""
import os
import tempfile
import time
from pathlib import Path

import pytest

from screensight.config import (
    AppConfig, AIEndpointConfig, load_config, CATEGORIES_23, ensure_dirs,
    PROJECT_ROOT,
)
from screensight.db import init_db, get_connection
from screensight.infra.screenshot import (
    list_monitors, capture_focused_monitor, capture_all_monitors,
    compress_for_archive, image_to_bytes,
)


class TestConfig:
    """配置加载测试。"""

    def test_load_config_from_env_local(self):
        """能从 .env.local 分段解析出 LLM 与 VLM 配置。"""
        env_path = PROJECT_ROOT / ".env.local"
        if not env_path.exists():
            pytest.skip("无 .env.local，跳过")
        config = load_config()
        # LLM 与 VLM 应是不同端点（验证分段解析生效，而非后者覆盖前者）
        assert config.llm.model != "" or config.vlm.model != "", "模型名应非空"
        assert config.llm.base_url != "" or config.vlm.base_url != ""
        print(f"LLM model={config.llm.model}, VLM model={config.vlm.model}")
        # 验证两段确实分离（base_url 不同）
        if config.llm.base_url and config.vlm.base_url:
            assert config.llm.base_url != config.vlm.base_url, \
                "LLM 与 VLM base_url 应不同（验证分段解析）"

    def test_categories_23(self):
        """23 类一级分类完整。"""
        assert len(CATEGORIES_23) == 23
        assert "编码开发" in CATEGORIES_23
        assert "其他/空闲" in CATEGORIES_23

    def test_ensure_dirs(self):
        """目录创建。"""
        ensure_dirs()
        from screensight.config import DATA_DIR, SCREENSHOT_DIR, MODEL_CACHE_DIR
        assert DATA_DIR.exists()
        assert SCREENSHOT_DIR.exists()
        assert MODEL_CACHE_DIR.exists()


class TestDb:
    """数据库测试。"""

    def test_init_db_creates_tables(self, tmp_path):
        """初始化数据库创建所有表。"""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        expected = {
            "captures", "recognitions", "activity_segments",
            "reports", "settings", "usage_stats", "search_index",
        }
        assert expected.issubset(tables), f"缺失表: {expected - tables}"
        # 向量表（sqlite-vec 扩展可用时存在）
        if "recognition_vectors" in tables:
            print("sqlite-vec 向量表已创建")
        conn.close()

    def test_init_db_idempotent(self, tmp_path):
        """重复初始化不报错。"""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        init_db(db_path)  # 不应抛异常


class TestScreenshot:
    """截图测试。"""

    def test_list_monitors(self):
        """能列出显示器。"""
        monitors = list_monitors()
        assert len(monitors) >= 1, "至少应有 1 个显示器"
        print(f"检测到 {len(monitors)} 个显示器")
        for m in monitors:
            print(f"  屏 {m.index}: {m.width}x{m.height}, primary={m.is_primary}")

    def test_capture_focused(self):
        """能截取焦点屏。"""
        result = capture_focused_monitor()
        assert result is not None
        assert result.image is not None
        assert result.image.width > 0
        print(f"焦点屏截图: {result.image.width}x{result.image.height}, focused={result.is_focused}")

    def test_capture_all(self):
        """能截取所有屏。"""
        results = capture_all_monitors()
        assert len(results) >= 1
        # 至少一个是焦点屏
        focused = [r for r in results if r.is_focused]
        assert len(focused) == 1, "应有且仅有一个焦点屏"
        print(f"截取 {len(results)} 屏，焦点屏序号 {focused[0].monitor.index}")

    def test_compress_for_archive(self):
        """存档压缩能减小体积。"""
        result = capture_focused_monitor()
        if result is None:
            pytest.skip("无法截图")
        original = image_to_bytes(result.image, "PNG")
        compressed = compress_for_archive(result.image, scale_percent=50, quality=70)
        ratio = len(compressed) / len(original)
        print(f"原图 {len(original)} bytes -> 存档 {len(compressed)} bytes, 压缩比 {ratio:.2%}")
        assert len(compressed) < len(original), "压缩后应更小"


class TestActivityMonitor:
    """键鼠活动检测测试。"""

    def test_activity_monitor_basic(self):
        """活动监控器基本功能。"""
        from screensight.infra.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor()
        monitor.start()
        try:
            time.sleep(0.5)
            # 启动后应认为近期有活动（初始化时间）
            assert monitor.seconds_since_last_activity() < 10
            assert not monitor.is_idle(idle_threshold=300)
            print(f"距上次活动 {monitor.seconds_since_last_activity():.2f}s")
        finally:
            monitor.stop()
