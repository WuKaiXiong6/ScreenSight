# 文件路径：backend/tests/test_recognize_integration.py
# 文件作用：VLM 识别端到端集成测试（真实截图+真实VLM调用）
# 最后更新时间：2026-06-28-2005
"""VLM 识别集成测试。

验证截图 → VLM 识别 → 结果解析 → 向量化 的完整链路。
需要 .env.local 配置有效的 VLM 凭证。
"""
import time

import pytest

from screensight.config import load_config
from screensight.db import set_db_path, init_db
from screensight.infra.screenshot import capture_focused_monitor
from screensight.services.recognize_service import RecognizeService
from screensight.services.activity_service import ActivityService
from screensight.config import Settings


@pytest.fixture
def vlm_config():
    """加载真实配置，无 VLM 凭证则跳过。"""
    config = load_config()
    if not config.vlm.api_key or not config.vlm.model:
        pytest.skip("无 VLM 凭证，跳过集成测试")
    return config


def test_recognize_real_screenshot(vlm_config, tmp_path):
    """真实截图 + 真实 VLM 识别。"""
    set_db_path(tmp_path / "t.db")
    init_db(tmp_path / "t.db")
    # 截图
    screenshot = capture_focused_monitor()
    assert screenshot is not None
    # 识别
    service = RecognizeService(vlm_config)
    result = service.recognize(screenshot)
    assert result is not None, "VLM 识别应返回结果"
    # 验证结构
    assert result.category, "类别应非空"
    assert 0.0 <= result.confidence <= 1.0
    assert result.tokens_used > 0
    print(f"\n识别结果: category={result.category}, sub_desc={result.sub_desc}")
    print(f"  object_name={result.object_name}, activity={result.activity}")
    print(f"  confidence={result.confidence}, tokens={result.tokens_used}")


def test_recognize_and_store(vlm_config, tmp_path):
    """识别并存储 + 活动合并。"""
    set_db_path(tmp_path / "t.db")
    init_db(tmp_path / "t.db")
    from screensight.repositories import insert_capture, get_recognition
    screenshot = capture_focused_monitor()
    assert screenshot is not None
    captured_at = "2026-06-28T20:00:00+08:00"
    cid = insert_capture(captured_at, 1, True, screenshot.image.width, screenshot.image.height)
    service = RecognizeService(vlm_config)
    rid = service.recognize_and_store(cid, screenshot)
    assert rid is not None
    rec = get_recognition(rid)
    assert rec is not None
    assert rec["category"]
    # 活动合并
    activity_svc = ActivityService(Settings())
    sid = activity_svc.merge_recognition(
        cid, captured_at, rec["category"], rec["sub_desc"], rec["object_name"]
    )
    assert sid > 0
    # 等待异步向量化
    time.sleep(3)
    from screensight.repositories import search_similar_recognitions
    # 向量可能已入库
    results = search_similar_recognitions(
        __import__("screensight.infra.embedder", fromlist=["get_embedder"]).get_embedder().encode_one("测试"),
        top_k=5,
    )
    print(f"向量检索结果数: {len(results)}")
