# 文件路径：backend/tests/test_report_search.py
# 文件作用：报告与搜索服务测试
# 最后更新时间：2026-07-02-1209
"""报告与搜索服务测试。"""
import json

from screensight.config import AppConfig, Settings
from screensight.db import set_db_path, init_db
from screensight.repositories import (
    insert_capture, insert_recognition, insert_segment,
    insert_recognition_vector, set_segment_end,
)
from screensight.services.report_service import ReportService
from screensight.services.search_service import SearchService
from screensight.infra.timeutil import now_iso, iso_to_dt
from datetime import timedelta


def _seed_data():
    """构造测试数据：3个时段（编码开发2h、网页浏览1h、视频1h）。"""
    base = iso_to_dt(now_iso()).replace(hour=9, minute=0, second=0, microsecond=0)
    # 时段1: 9:00-11:00 编码开发 ScreenSight
    cid = insert_capture(base.isoformat(), 1, True, 1920, 1080)
    insert_recognition(cid, "编码开发", "Python", "ScreenSight", "写代码", 0.9, False, "{}")
    insert_recognition_vector(1, [0.1] * 1024)
    sid1 = insert_segment(base.isoformat(), "编码开发", "Python", "ScreenSight", [cid])
    set_segment_end(sid1, (base + timedelta(hours=2)).isoformat())
    # 时段2: 11:00-12:00 网页浏览
    cid2 = insert_capture((base + timedelta(hours=2)).isoformat(), 1, True, 1920, 1080)
    insert_recognition(cid2, "网页浏览", "", "GitHub", "浏览GitHub", 0.85, False, "{}")
    insert_recognition_vector(2, [0.2] * 1024)
    sid2 = insert_segment((base + timedelta(hours=2)).isoformat(), "网页浏览", "", "GitHub", [cid2])
    set_segment_end(sid2, (base + timedelta(hours=3)).isoformat())
    # 时段3: 14:00-15:00 视频
    cid3 = insert_capture((base + timedelta(hours=5)).isoformat(), 1, True, 1920, 1080)
    insert_recognition(cid3, "视频/电影", "", "流浪地球", "看电影", 0.7, False, "{}")
    insert_recognition_vector(3, [0.3] * 1024)
    sid3 = insert_segment((base + timedelta(hours=5)).isoformat(), "视频/电影", "", "流浪地球", [cid3])
    set_segment_end(sid3, (base + timedelta(hours=6)).isoformat())
    # 全文索引
    SearchService.index_recognition(1)
    SearchService.index_recognition(2)
    SearchService.index_recognition(3)
    return base


class TestReportStats:
    """报告规则统计测试（不依赖 LLM，验证准确性）。"""

    def test_compute_stats_accuracy(self, tmp_path):
        """规则统计时长占比准确。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        base = _seed_data()
        svc = ReportService(AppConfig())
        period = svc.get_period("daily", base)
        stats = svc.compute_stats(period)
        # 总时长 = 2h(编码) + 1h(网页) + 1h(视频) = 4h
        assert stats["total_seconds"] == 4 * 3600, f"期望14400, 实际{stats['total_seconds']}"
        assert stats["total_hours"] == "4.0h"
        # 编码开发占比 50%
        coding = [c for c in stats["by_category"] if c["category"] == "编码开发"][0]
        assert coding["hours"] == "2.0h"
        assert coding["percentage"] == "50.0"
        # Top 对象
        top = stats["top_objects"][0]
        assert top["object_name"] == "ScreenSight"
        assert top["hours"] == "2.0h"

    def test_generate_report_without_llm(self, tmp_path):
        """无 LLM 时生成纯规则报告。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        base = _seed_data()
        svc = ReportService(AppConfig())  # 无 LLM 配置
        report = svc.generate_report("daily", base, use_llm=False)
        assert report["stats"]["total_seconds"] == 4 * 3600
        assert report["llm_summary"] is None
        # 持久化
        reports = svc.list_reports()
        assert len(reports) == 1

    def test_export_markdown(self, tmp_path):
        """Markdown 导出。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        base = _seed_data()
        svc = ReportService(AppConfig())
        report = svc.generate_report("daily", base, use_llm=False)
        md = svc.export_markdown(report)
        assert "# 日报告" in md or "# 日报告" in md
        assert "编码开发" in md
        assert "ScreenSight" in md
        assert "50.0%" in md
        # 时长单位不应重复拼接（后端 hours 字段已含单位，导出不得再补 "小时"/"h"）
        assert "小时 小时" not in md, "总活跃时长出现重复单位"
        assert "hh" not in md, "分类/对象时长出现重复 h"
        assert "分 小时" not in md, "分钟值后被追加 小时"
        assert "分h" not in md, "分钟值后被追加 h"
        assert "时长(小时)" not in md, "表头不应硬编码单位(小时)"


class TestSearch:
    """搜索服务测试。"""

    def test_keyword_search(self, tmp_path):
        """关键词搜索。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        _seed_data()
        svc = SearchService(AppConfig())
        # 搜 "代码"
        results = svc.keyword_search("代码")
        assert len(results) >= 1
        assert any(r["category"] == "编码开发" for r in results)
        # 搜 "电影"
        results = svc.keyword_search("电影")
        assert len(results) >= 1
        assert results[0]["category"] == "视频/电影"

    def test_keyword_search_with_filter(self, tmp_path):
        """关键词搜索 + 类目筛选。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        _seed_data()
        svc = SearchService(AppConfig())
        results = svc.keyword_search("浏览", category="网页浏览")
        assert len(results) >= 1
        assert all(r["category"] == "网页浏览" for r in results)

    def test_list_categories_objects(self, tmp_path):
        """类别与对象列表。"""
        set_db_path(tmp_path / "t.db")
        init_db(tmp_path / "t.db")
        _seed_data()
        svc = SearchService(AppConfig())
        cats = svc.list_categories()
        assert len(cats) == 3
        objs = svc.list_objects()
        assert len(objs) == 3
        assert any(o["object_name"] == "ScreenSight" for o in objs)
