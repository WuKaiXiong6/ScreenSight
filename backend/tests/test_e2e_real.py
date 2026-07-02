# 文件路径：backend/tests/test_e2e_real.py
# 文件作用：端到端真实链路测试（真实截图+真实VLM/LLM+完整流程）
# 最后更新时间：2026-06-28-2015
"""端到端真实链路测试。

验证：截图 → VLM识别 → 活动合并 → 报告生成(规则+LLM) → 关键词搜索 → RAG问答
全部使用真实云端 API 与本地 embedding。
"""
import time

import pytest

from screensight.config import load_config, AppConfig
from screensight.db import set_db_path, init_db
from screensight.infra.screenshot import capture_focused_monitor
from screensight.infra.timeutil import now_iso, iso_to_dt
from screensight.repositories import get_recognition, set_segment_end
from screensight.services.recognize_service import RecognizeService
from screensight.services.activity_service import ActivityService
from screensight.services.report_service import ReportService
from screensight.services.search_service import SearchService


@pytest.fixture
def e2e_env(tmp_path):
    """端到端环境：真实配置 + 隔离数据库。"""
    config = load_config()
    if not config.vlm.api_key:
        pytest.skip("无 VLM 凭证")
    set_db_path(tmp_path / "e2e.db")
    init_db(tmp_path / "e2e.db")
    return config


def test_full_pipeline(e2e_env):
    """完整链路：截图→识别→合并→报告→搜索→RAG。"""
    config = e2e_env
    # 1. 截图 + 识别 + 合并
    recognize_svc = RecognizeService(config)
    activity_svc = ActivityService(config.settings)
    screenshot = capture_focused_monitor()
    assert screenshot is not None
    captured_at = now_iso()
    from screensight.repositories import insert_capture
    cid = insert_capture(captured_at, screenshot.monitor.index, True,
                         screenshot.image.width, screenshot.image.height)
    rid = recognize_svc.recognize_and_store(cid, screenshot)
    assert rid is not None, "识别应成功"
    rec = get_recognition(rid)
    assert rec is not None
    print(f"\n[1] 识别: {rec['category']} / {rec['object_name']} / {rec['activity']}")

    # 合并到时段
    sid = activity_svc.merge_recognition(
        cid, captured_at, rec["category"], rec["sub_desc"], rec["object_name"]
    )
    # 设置时段结束（模拟持续2小时）
    from screensight.infra.timeutil import now_dt
    from datetime import timedelta
    set_segment_end(sid, (now_dt() + timedelta(hours=2)).isoformat())

    # 2. 报告生成（规则 + LLM）
    report_svc = ReportService(config)
    report = report_svc.generate_report("daily", use_llm=True)
    assert report["stats"]["total_seconds"] > 0, "报告应有时长统计"
    print(f"[2] 报告: 总时长 {report['stats']['total_hours']}h, "
          f"LLM总结={'有' if report['llm_summary'] else '无'}")
    if report["llm_summary"]:
        print(f"    LLM总结: {report['llm_summary'][:80]}...")

    # 3. 关键词搜索
    search_svc = SearchService(config)
    # 用识别结果中的关键词搜索
    keyword = rec["category"][:2] if rec["category"] else "测试"
    results = search_svc.keyword_search(keyword)
    print(f"[3] 关键词搜索 '{keyword}': {len(results)} 条结果")

    # 4. RAG 问答（等向量化完成）
    time.sleep(8)  # 等待异步向量化
    rag = search_svc.rag_query("我今天在做什么？")
    print(f"[4] RAG问答: answer={rag['answer'][:80]}..., sources={len(rag['sources'])}")
    assert len(rag["sources"]) > 0, "RAG 应检索到来源"

    # 5. Markdown 导出
    md = report_svc.export_markdown(report)
    assert "日报告" in md
    assert rec["category"] in md
    print(f"[5] Markdown 导出: {len(md)} 字符")

    print("\n=== 端到端链路全部通过 ===")
