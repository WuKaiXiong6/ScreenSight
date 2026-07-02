# 文件路径：backend/screensight/api/search.py
# 文件作用：搜索 API，关键词搜索与 RAG 问答
# 最后更新时间：2026-07-02-1209
"""搜索 API。"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..app import get_context

router = APIRouter(tags=["search"])


@router.get("/search/keyword")
async def keyword_search(
    q: str = Query(..., description="关键词"),
    start: Optional[str] = Query(None, description="开始时间 ISO"),
    end: Optional[str] = Query(None, description="结束时间 ISO"),
    category: Optional[str] = Query(None),
    object_name: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(50, le=500),
):
    """关键词搜索。"""
    ctx = get_context()
    results = ctx.search_service.keyword_search(
        q, start=start, end=end, category=category,
        object_name=object_name, min_confidence=min_confidence, limit=limit,
    )
    return {"query": q, "count": len(results), "results": results}


class RagRequest(BaseModel):
    question: str
    start: Optional[str] = None
    end: Optional[str] = None
    category: Optional[str] = None
    min_confidence: Optional[float] = None
    top_k: int = 8
    retrieve_only: bool = False  # 仅检索来源不生成回答（省 token）


@router.post("/search/rag")
async def rag_query(req: RagRequest):
    """RAG 问答检索。retrieve_only=True 时跳过 LLM 生成。"""
    ctx = get_context()
    result = ctx.search_service.rag_query(
        req.question, start=req.start, end=req.end,
        category=req.category, min_confidence=req.min_confidence,
        top_k=req.top_k, retrieve_only=req.retrieve_only,
    )
    return result


@router.get("/search/facets")
async def get_facets():
    """获取搜索筛选项（类别与对象列表）。"""
    ctx = get_context()
    return {
        "categories": ctx.search_service.list_categories(),
        "objects": ctx.search_service.list_objects(),
    }
