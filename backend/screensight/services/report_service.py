# 文件路径：backend/screensight/services/report_service.py
# 文件作用：报告服务，规则统计(保准确)+LLM润色，生成小时报/日报/周报/月报
# 最后更新时间：2026-06-28-2010

"""报告服务。

规则统计保证数字准确（避免 LLM 幻觉），LLM 只接收聚合后的统计数据
生成自然语言总结与洞察。支持小时报/日报/周报/月报，可导出 MD。
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from jinja2 import Template

from ..config import AppConfig, PROMPT_DIR
from ..infra.ai_client import AIClient
from ..infra.timeutil import (
    LOCAL_TZ, now_iso, iso_to_dt, start_of_day, end_of_day,
    start_of_week, start_of_month, today_str,
)
from ..repositories import query_segments, get_db

logger = logging.getLogger(__name__)

_LLM_COST_PER_1K = 0.005


@dataclass
class ReportPeriod:
    """报告时段。"""
    report_type: str  # hourly/daily/weekly/monthly
    start: str
    end: str


def _format_hours(seconds: int) -> str:
    """秒转小时字符串（保留1位小数）。"""
    return f"{seconds / 3600:.1f}"


class ReportService:
    """报告服务。"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._llm_client: Optional[AIClient] = None
        self._polish_template = (PROMPT_DIR / "report_polish.md").read_text(encoding="utf-8")

    def _get_llm_client(self) -> AIClient:
        if self._llm_client is None:
            self._llm_client = AIClient(self._config.llm)
        return self._llm_client

    # ============ 时段计算 ============

    def get_period(self, report_type: str, ref_dt: Optional[datetime] = None) -> ReportPeriod:
        """根据报告类型计算时段。"""
        ref = ref_dt or datetime.now(LOCAL_TZ)
        if report_type == "hourly":
            start = ref.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif report_type == "daily":
            start = datetime(ref.year, ref.month, ref.day, tzinfo=LOCAL_TZ)
            end = start + timedelta(days=1)
        elif report_type == "weekly":
            monday = ref.date() - timedelta(days=ref.weekday())
            start = datetime(monday.year, monday.month, monday.day, tzinfo=LOCAL_TZ)
            end = start + timedelta(days=7)
        elif report_type == "monthly":
            start = datetime(ref.year, ref.month, 1, tzinfo=LOCAL_TZ)
            if ref.month == 12:
                end = datetime(ref.year + 1, 1, 1, tzinfo=LOCAL_TZ)
            else:
                end = datetime(ref.year, ref.month + 1, 1, tzinfo=LOCAL_TZ)
        else:
            raise ValueError(f"未知报告类型: {report_type}")
        return ReportPeriod(report_type, start.isoformat(timespec="seconds"),
                            end.isoformat(timespec="seconds"))

    # ============ 规则统计 ============

    def compute_stats(self, period: ReportPeriod) -> dict:
        """规则统计（保准确）。"""
        segments = query_segments(start=period.start, end=period.end, limit=10000)
        by_category: dict[str, int] = defaultdict(int)  # category -> seconds
        by_object: dict[str, int] = defaultdict(int)
        timeline: list[dict] = []
        total_seconds = 0
        low_conf_count = 0
        for seg in segments:
            dur = seg["duration_seconds"]
            total_seconds += dur
            by_category[seg["category"]] += dur
            obj = seg.get("object_name") or "(未命名)"
            by_object[obj] += dur
            if seg.get("is_low_confidence"):
                low_conf_count += 1
            timeline.append({
                "start": seg["start_time"],
                "end": seg["end_time"],
                "category": seg["category"],
                "object_name": seg.get("object_name") or "",
                "duration_seconds": dur,
            })
        # 分类占比
        cat_list = [
            {"category": c, "seconds": s, "hours": _format_hours(s),
             "percentage": f"{s / total_seconds * 100:.1f}" if total_seconds else "0.0"}
            for c, s in sorted(by_category.items(), key=lambda x: -x[1])
        ]
        obj_list = [
            {"object_name": o, "seconds": s, "hours": _format_hours(s)}
            for o, s in sorted(by_object.items(), key=lambda x: -x[1])[:10]
        ]
        return {
            "period_type": period.report_type,
            "period_start": period.start,
            "period_end": period.end,
            "total_seconds": total_seconds,
            "total_hours": _format_hours(total_seconds),
            "by_category": cat_list,
            "top_objects": obj_list,
            "timeline": timeline,
            "segment_count": len(segments),
            "low_confidence_count": low_conf_count,
        }

    # ============ LLM 润色 ============

    def llm_polish(self, stats: dict) -> Optional[str]:
        """LLM 生成自然语言总结。失败时返回 None（降级为纯规则统计）。"""
        prompt = Template(self._polish_template).render(**stats)
        try:
            resp = self._get_llm_client().chat(
                messages=[
                    {"role": "system", "content": "你是时间管理分析助手，生成简洁有洞察的总结。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.4,
            )
            from ..repositories import record_usage
            record_usage("llm", 1, resp.total_tokens, resp.total_tokens / 1000 * _LLM_COST_PER_1K)
            return resp.content.strip()
        except Exception as e:
            logger.error("LLM 报告润色失败: %s", e)
            return None

    # ============ 生成报告 ============

    def generate_report(
        self, report_type: str, ref_dt: Optional[datetime] = None, use_llm: bool = True
    ) -> dict:
        """生成一份报告。"""
        period = self.get_period(report_type, ref_dt)
        stats = self.compute_stats(period)
        llm_summary = None
        if use_llm and stats["total_seconds"] > 0 and self._config.llm.api_key:
            llm_summary = self.llm_polish(stats)
        report = {
            "report_type": report_type,
            "period_start": period.start,
            "period_end": period.end,
            "stats": stats,
            "llm_summary": llm_summary,
            "generated_at": now_iso(),
        }
        # 持久化
        self._save_report(report)
        return report

    def _save_report(self, report: dict) -> int:
        """保存报告到数据库。"""
        from ..repositories import get_db
        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO reports
                   (report_type, period_start, period_end, stats_json, llm_summary,
                    generated_at, is_manual)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (report["report_type"], report["period_start"], report["period_end"],
                 json.dumps(report["stats"], ensure_ascii=False),
                 report["llm_summary"], report["generated_at"]),
            )
            return cur.lastrowid

    def list_reports(
        self, report_type: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """列出报告。"""
        from ..repositories import get_db
        with get_db() as conn:
            if report_type:
                rows = conn.execute(
                    "SELECT * FROM reports WHERE report_type=? ORDER BY period_start DESC LIMIT ?",
                    (report_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY period_start DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["stats"] = json.loads(d["stats_json"])
                results.append(d)
            return results

    def get_report(self, report_id: int) -> Optional[dict]:
        from ..repositories import get_db
        with get_db() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["stats"] = json.loads(d["stats_json"])
            return d

    # ============ 导出 ============

    def export_markdown(self, report: dict) -> str:
        """导出为 Markdown。"""
        stats = report["stats"]
        lines = [
            f"# {self._type_name(report['report_type'])}报告",
            f"",
            f"**时段**：{report['period_start']} 至 {report['period_end']}",
            f"**生成时间**：{report['generated_at']}",
            f"**总活跃时长**：{stats['total_hours']} 小时",
            f"",
            "## 分类时长与占比",
            "",
            "| 类别 | 时长(小时) | 占比 |",
            "|---|---|---|",
        ]
        for c in stats["by_category"]:
            lines.append(f"| {c['category']} | {c['hours']} | {c['percentage']}% |")
        lines.append("")
        lines.append("## Top 项目/对象")
        lines.append("")
        lines.append("| 项目/对象 | 时长(小时) |")
        lines.append("|---|---|")
        for o in stats["top_objects"]:
            lines.append(f"| {o['object_name']} | {o['hours']} |")
        lines.append("")
        if report.get("llm_summary"):
            lines.append("## 总结与洞察")
            lines.append("")
            lines.append(report["llm_summary"])
            lines.append("")
        lines.append("## 时间轴活动列表")
        lines.append("")
        for t in stats["timeline"]:
            lines.append(f"- {t['start']} ~ {t['end']} {t['category']}"
                         f"{' - ' + t['object_name'] if t['object_name'] else ''}")
        return "\n".join(lines)

    @staticmethod
    def _type_name(t: str) -> str:
        return {"hourly": "小时", "daily": "日", "weekly": "周", "monthly": "月"}.get(t, t)
