# 文件路径：backend/tests/test_repositories.py
# 文件作用：数据访问层单元测试
# 最后更新时间：2026-07-02-1209
"""仓储层测试。"""
import json
from screensight.db import init_db, get_connection, set_db_path
from screensight.repositories import (
    insert_capture, update_capture_recognition, get_capture,
    insert_recognition, get_recognition, insert_recognition_vector,
    search_similar_recognitions,
    get_open_segment, insert_segment, update_segment_append,
    close_segment, close_all_open_segments, query_segments, delete_segment,
    get_setting, set_setting, get_all_settings,
    record_usage, query_usage, query_usage_hourly, query_usage_trend, query_usage_breakdown,
    get_recent_activity,
)
from screensight.infra.timeutil import now_iso


def test_capture_crud(tmp_path):
    """截图记录增改查。"""
    init_db(tmp_path / "t.db")
    cid = insert_capture(now_iso(), 1, True, 1920, 1080, archive_path="/tmp/a.webp")
    assert cid > 0
    assert get_capture(cid)["recognition_status"] == "pending"
    update_capture_recognition(cid, "success", recognition_id=99)
    assert get_capture(cid)["recognition_status"] == "success"
    assert get_capture(cid)["recognition_id"] == 99


def test_recognition_and_vector(tmp_path):
    """识别结果与向量插入检索。"""
    init_db(tmp_path / "t.db")
    cid = insert_capture(now_iso(), 1, True, 1920, 1080)
    rid = insert_recognition(cid, "编码开发", "Python-Test", "TestProj",
                             "编辑main.py", 0.9, False, "{}")
    assert rid > 0
    assert get_recognition(rid)["category"] == "编码开发"
    # 向量
    vec = [0.1] * 1024
    ok = insert_recognition_vector(rid, vec)
    assert ok
    # 检索（应能命中自身）
    results = search_similar_recognitions(vec, top_k=5)
    assert any(r["id"] == rid for r in results)


def test_segment_merge(tmp_path):
    """活动时段增量合并。"""
    init_db(tmp_path / "t.db")
    t0 = now_iso()
    # 第一条：新建时段
    cid1 = insert_capture(t0, 1, True, 1920, 1080)
    seg = get_open_segment("编码开发", "ScreenSight")
    assert seg is None
    sid = insert_segment(t0, "编码开发", "Python", "ScreenSight", [cid1])
    # 第二条：可合并（同类别同对象）
    seg = get_open_segment("编码开发", "ScreenSight")
    assert seg is not None
    assert seg.id == sid
    cid2 = insert_capture(now_iso(), 1, True, 1920, 1080)
    update_segment_append(sid, now_iso(), cid2)
    seg = get_open_segment("编码开发", "ScreenSight")
    assert seg.capture_count == 2
    # 不同对象：新建时段
    cid3 = insert_capture(now_iso(), 1, True, 1920, 1080)
    other = get_open_segment("编码开发", "OtherProj")
    assert other is None
    sid2 = insert_segment(now_iso(), "编码开发", "Python", "OtherProj", [cid3])
    assert sid2 != sid


def test_close_all_open_segments(tmp_path):
    """关闭所有未关闭时段。"""
    init_db(tmp_path / "t.db")
    t0 = now_iso()
    insert_segment(t0, "编码开发", "", "A", [1])
    insert_segment(t0, "网页浏览", "", "B", [2])
    closed = close_all_open_segments()
    assert closed == 2
    assert query_segments()[0]["is_closed"] == 1


def test_query_segments_filter(tmp_path):
    """时段查询筛选。"""
    init_db(tmp_path / "t.db")
    t0 = now_iso()
    cid = insert_capture(t0, 1, True, 1920, 1080)
    insert_recognition(cid, "编码开发", "", "ScreenSight", "coding", 0.9, False, "{}")
    insert_segment(t0, "编码开发", "", "ScreenSight", [cid])
    # 按类别筛选
    res = query_segments(category="编码开发")
    assert len(res) == 1
    # 按对象筛选
    res = query_segments(object_name="ScreenSight")
    assert len(res) == 1
    # 不匹配
    res = query_segments(category="游戏")
    assert len(res) == 0


def test_delete_segment_cascade(tmp_path):
    """删除时段级联删除关联数据。"""
    init_db(tmp_path / "t.db")
    t0 = now_iso()
    cid = insert_capture(t0, 1, True, 1920, 1080, archive_path="/tmp/x.webp")
    rid = insert_recognition(cid, "编码开发", "", "P", "c", 0.8, False, "{}")
    insert_recognition_vector(rid, [0.1] * 1024)
    sid = insert_segment(t0, "编码开发", "", "P", [cid])
    paths = delete_segment(sid)
    assert paths == ["/tmp/x.webp"]
    assert get_capture(cid) is None
    assert get_recognition(rid) is None


def test_settings(tmp_path):
    """设置读写。"""
    init_db(tmp_path / "t.db")
    assert get_setting("nope", "default") == "default"
    set_setting("capture_interval_active", "30")
    assert get_setting("capture_interval_active") == "30"
    all_s = get_all_settings()
    assert all_s["capture_interval_active"] == "30"


def test_usage_stats(tmp_path):
    """用量统计聚合。"""
    init_db(tmp_path / "t.db")
    record_usage("vlm", 1, 500, 0.01, stat_date="2026-06-28")
    record_usage("vlm", 2, 800, 0.02, stat_date="2026-06-28")  # 同天累加
    record_usage("llm", 1, 100, 0.001, stat_date="2026-06-28")
    rows = query_usage()
    vlm = [r for r in rows if r["api_type"] == "vlm"][0]
    assert vlm["call_count"] == 3
    assert vlm["tokens_used"] == 1300
    assert len(rows) == 2


def test_usage_hourly_trend_breakdown(tmp_path):
    """小时级用量、趋势与占比查询。"""
    set_db_path(tmp_path / "t.db")
    init_db(tmp_path / "t.db")
    # 双写：record_usage 同时写天表与小时表
    record_usage("vlm", 1, 500, 0.01, stat_date="2026-07-01")
    record_usage("vlm", 2, 800, 0.02, stat_date="2026-07-02")
    record_usage("llm", 1, 100, 0.005, stat_date="2026-07-02")
    # 小时级：stat_date 传日期时小时取该日 00:00 前缀
    hourly = query_usage_hourly(start_hour="2026-07-01 00:00", end_hour="2026-07-03 00:00")
    assert len(hourly) >= 2  # vlm(07-01) + vlm(07-02) + llm(07-02)
    assert any(h["api_type"] == "vlm" and h["stat_hour"].startswith("2026-07-01") for h in hourly)
    # 趋势：按天聚合
    trend = query_usage_trend(start_date="2026-07-01", end_date="2026-07-03")
    assert len(trend) == 2  # 07-01, 07-02
    d2 = [t for t in trend if t["date"] == "2026-07-02"][0]
    assert d2["total_cost"] == 0.025
    assert d2["total_calls"] == 3
    # 占比：按 api_type
    bd = query_usage_breakdown(start_date="2026-07-01", end_date="2026-07-03")
    vlm_bd = [b for b in bd if b["api_type"] == "vlm"][0]
    assert vlm_bd["total_cost"] == 0.03
    assert vlm_bd["total_calls"] == 3


def test_recent_activity(tmp_path):
    """最近活动信息查询。"""
    set_db_path(tmp_path / "t.db")
    init_db(tmp_path / "t.db")
    t0 = now_iso()
    # 一条成功识别的截屏
    cid = insert_capture(t0, 1, True, 1920, 1080)
    rid = insert_recognition(cid, "编码开发", "Python", "ScreenSight", "写代码", 0.9, False, "{}")
    update_capture_recognition(cid, "success", recognition_id=rid)
    # 一条失败截屏（最近 30 分钟内）
    insert_capture(t0, 2, False, 1920, 1080)
    # 一个活动段
    sid = insert_segment(t0, "编码开发", "Python", "ScreenSight", [cid])
    close_segment(sid)
    # 今日费用
    from screensight.infra.timeutil import today_str
    record_usage("vlm", 1, 100, 0.05, stat_date=today_str())
    info = get_recent_activity()
    assert info["last_capture_at"] is not None
    assert info["last_recognition_at"] is not None
    assert info["last_data_date"] is not None
    assert info["today_cost"] == 0.05
    # 失败截屏：上面第二条未 update 状态，默认 pending 而非 failed，故应为 0
    assert info["recent_error_count"] == 0
