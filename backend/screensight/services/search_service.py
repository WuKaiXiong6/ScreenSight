# 文件路径：backend/screensight/services/search_service.py
# 文件作用：搜索服务，关键词搜索(FTS5) + RAG问答检索(向量+LLM)
# 最后更新时间：2026-07-02-1209

"""搜索与 RAG 服务。

1. 关键词搜索：基于 SQLite FTS5 全文索引，覆盖识别描述+报告文本+标签对象名
2. RAG 问答：用户问题向量化 → sqlite-vec 检索 top-K → LLM 生成回答
3. 多维筛选：时间范围/类目/项目/置信度
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from ..config import AppConfig
from ..infra.ai_client import AIClient
from ..infra.embedder import get_embedder
from ..infra.timeutil import now_iso
from ..repositories import (
    search_similar_recognitions, get_db, record_usage,
)

logger = logging.getLogger(__name__)

_LLM_COST_PER_1K = 0.005


class SearchService:
    """搜索与 RAG 服务。"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._llm_client: Optional[AIClient] = None

    def _get_llm_client(self) -> AIClient:
        if self._llm_client is None:
            self._llm_client = AIClient(self._config.llm)
        return self._llm_client

    # ============ 关键词搜索 ============

    def keyword_search(
        self,
        query: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        category: Optional[str] = None,
        object_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50,
    ) -> list[dict]:
        """关键词搜索识别记录。

        用 LIKE 模糊匹配识别描述文本（兼容任意长度中文词），
        再叠加多维筛选。FTS5 的 trigram 分词对 2 字中文词支持差，
        故关键词搜索直接用 LIKE，向量检索由 RAG 承担。
        """
        with get_db() as conn:
            like_pattern = f"%{query.strip()}%"
            sql = """
                SELECT rec.id, rec.capture_id, rec.category, rec.sub_desc,
                       rec.object_name, rec.activity, rec.confidence,
                       rec.is_low_confidence, rec.created_at,
                       c.captured_at, c.archive_path
                FROM recognitions rec
                LEFT JOIN captures c ON c.id = rec.capture_id
                WHERE 1=1
            """
            params: list = []
            sql += " AND (rec.activity LIKE ? OR rec.sub_desc LIKE ? OR rec.object_name LIKE ? OR rec.category LIKE ?)"
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])
            if start:
                sql += " AND c.captured_at >= ?"
                params.append(start)
            if end:
                sql += " AND c.captured_at < ?"
                params.append(end)
            if category:
                sql += " AND rec.category = ?"
                params.append(category)
            if object_name:
                sql += " AND rec.object_name = ?"
                params.append(object_name)
            if min_confidence is not None:
                sql += " AND rec.confidence >= ?"
                params.append(min_confidence)
            sql += " ORDER BY rec.created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ============ RAG 问答 ============

    def rag_query(
        self,
        question: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        category: Optional[str] = None,
        min_confidence: Optional[float] = None,
        top_k: int = 8,
        retrieve_only: bool = False,
    ) -> dict:
        """RAG 问答检索。

        Args:
            retrieve_only: 为 True 时仅返回检索来源，跳过 LLM 生成（省 token）
        Returns:
            {"answer": str, "sources": [list of recognition records]}
        """
        # 1. 问题向量化
        try:
            qvec = get_embedder().encode_one(question)
        except Exception as e:
            logger.error("问题向量化失败: %s", e)
            return {"answer": "抱歉，检索服务暂时不可用。", "sources": []}
        # 2. 向量检索
        candidates = search_similar_recognitions(qvec, top_k=top_k * 2)
        # 3. 叠加筛选
        filtered = []
        for c in candidates:
            if start and c.get("created_at", "") < start:
                continue
            if end and c.get("created_at", "") >= end:
                continue
            if category and c.get("category") != category:
                continue
            if min_confidence is not None and (c.get("confidence") or 0) < min_confidence:
                continue
            filtered.append(c)
            if len(filtered) >= top_k:
                break
        if not filtered:
            return {"answer": "未找到相关的历史记录。", "sources": []}
        # 4. LLM 生成回答（retrieve_only 模式跳过，省 token）
        sources = [
            {
                "id": c.get("id"),
                "category": c.get("category"),
                "object_name": c.get("object_name"),
                "activity": c.get("activity"),
                "created_at": c.get("created_at"),
                "distance": c.get("distance"),
            }
            for c in filtered
        ]
        if retrieve_only:
            return {"answer": "", "sources": sources}
        answer = self._generate_answer(question, filtered)
        return {"answer": answer, "sources": sources}

    def _generate_answer(self, question: str, sources: list[dict]) -> str:
        """基于检索结果生成回答。"""
        context_lines = []
        for i, s in enumerate(sources, 1):
            context_lines.append(
                f"{i}. [{s.get('created_at', '')}] {s.get('category', '')} - "
                f"{s.get('object_name', '')}: {s.get('activity', '')}"
            )
        context = "\n".join(context_lines)
        prompt = (
            f"用户问题：{question}\n\n"
            f"以下是检索到的历史屏幕活动记录：\n{context}\n\n"
            f"请根据这些记录回答用户问题。如果记录不足以回答，请如实说明。"
            f"回答要简洁，可引用记录中的时间。"
        )
        try:
            resp = self._get_llm_client().chat(
                messages=[
                    {"role": "system", "content": "你是基于用户屏幕活动历史的问答助手。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.3,
            )
            record_usage("llm", 1, resp.total_tokens, resp.total_tokens / 1000 * _LLM_COST_PER_1K)
            return resp.content.strip()
        except Exception as e:
            logger.error("RAG 回答生成失败: %s", e)
            return "抱歉，回答生成失败，但已检索到相关记录（见来源列表）。"

    # ============ 索引维护 ============

    @staticmethod
    def index_recognition(recognition_id: int, conn=None) -> None:
        """将识别结果加入全文索引。"""
        own = conn is None
        if own:
            ctx = get_db()
            conn = ctx.__enter__()
        try:
            row = conn.execute(
                "SELECT id, activity, sub_desc, object_name, category FROM recognitions WHERE id=?",
                (recognition_id,),
            ).fetchone()
            if not row:
                return
            content = " ".join(filter(None, [
                row["activity"], row["sub_desc"], row["object_name"], row["category"],
            ]))
            conn.execute(
                "INSERT INTO search_index(content, source_type, source_id) VALUES (?, 'recognition', ?)",
                (content, str(recognition_id)),
            )
        finally:
            if own:
                conn.commit()

    def list_categories(self) -> list[dict]:
        """列出所有出现过的类别及其记录数。"""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) AS cnt FROM recognitions GROUP BY category ORDER BY cnt DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def list_objects(self) -> list[dict]:
        """列出所有出现过的项目/对象名。"""
        with get_db() as conn:
            rows = conn.execute(
                """SELECT object_name, COUNT(*) AS cnt FROM recognitions
                   WHERE object_name != '' GROUP BY object_name ORDER BY cnt DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
