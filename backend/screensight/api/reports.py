# 文件路径：backend/screensight/api/reports.py
# 文件作用：报告 API，生成/查询/导出报告
# 最后更新时间：2026-06-28-2015
"""报告 API。"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..app import get_context
from ..infra.timeutil import LOCAL_TZ, parse_date

router = APIRouter(tags=["reports"])


class GenerateRequest(BaseModel):
    report_type: str  # hourly/daily/weekly/monthly
    date: Optional[str] = None  # YYYY-MM-DD
    use_llm: bool = True


@router.get("/reports")
async def list_reports(
    report_type: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
):
    """列出报告。"""
    ctx = get_context()
    return ctx.report_service.list_reports(report_type=report_type, limit=limit)


@router.get("/reports/{report_id}")
async def get_report(report_id: int):
    """获取报告详情。"""
    ctx = get_context()
    report = ctx.report_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    return report


@router.post("/reports/generate")
async def generate_report(req: GenerateRequest):
    """手动生成报告。"""
    ctx = get_context()
    ref_dt = None
    if req.date:
        d = parse_date(req.date)
        if d is None:
            raise HTTPException(400, "日期格式应为 YYYY-MM-DD")
        ref_dt = datetime(d.year, d.month, d.day, tzinfo=LOCAL_TZ)
    report = ctx.report_service.generate_report(req.report_type, ref_dt, use_llm=req.use_llm)
    return report


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: int,
    format: str = Query("md", pattern="^(md|pdf)$"),
):
    """导出报告。"""
    ctx = get_context()
    report = ctx.report_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    if format == "md":
        md = ctx.report_service.export_markdown(report)
        return PlainTextResponse(md, media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f"attachment; filename=report_{report_id}.md"})
    # PDF 暂未实现（需 weasyprint，体积大）
    raise HTTPException(501, "PDF 导出暂未启用，请安装 weasyprint 后使用")
