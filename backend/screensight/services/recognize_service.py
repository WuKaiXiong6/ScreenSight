# 文件路径：backend/screensight/services/recognize_service.py
# 文件作用：VLM 识别服务，调用云端 VLM 识别屏幕行为，解析结构化结果
# 最后更新时间：2026-06-28-2005

"""VLM 识别服务。

负责将焦点屏截图送云端 VLM，解析返回的 JSON 为结构化识别结果，
处理失败重试、用量记录、向量化触发。
识别与向化解耦：识别成功后异步触发向量化。
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import AppConfig, CATEGORIES_23, PROMPT_DIR, Settings
from ..infra.ai_client import AIClient
from ..infra.embedder import get_embedder
from ..infra.screenshot import ScreenshotResult, image_to_bytes
from ..infra.timeutil import now_iso
from ..repositories import (
    insert_recognition, insert_recognition_vector, update_capture_recognition,
    record_usage,
)

logger = logging.getLogger(__name__)

# 预估单价（元/千 token），仅用于费用统计展示，非真实账单
_VLM_COST_PER_1K = 0.02


@dataclass
class RecognitionResult:
    """识别结果。"""
    category: str
    sub_desc: str
    object_name: str
    activity: str
    confidence: float
    is_low_confidence: bool
    raw_response: str
    tokens_used: int
    cost_estimate: float


def _load_recognize_prompt() -> str:
    """加载识别 Prompt 模板。"""
    path = PROMPT_DIR / "recognize.md"
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> Optional[dict]:
    """从 VLM 输出中提取 JSON 对象。

    VLM 可能输出纯 JSON 或带 markdown 代码块，统一提取第一个 {...}。
    """
    if not text:
        return None
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 提取代码块内的 JSON
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 提取第一个 {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _normalize_category(category: str) -> str:
    """归一化类别名，匹配 23 类。"""
    if category in CATEGORIES_23:
        return category
    # 模糊匹配：包含关系
    for c in CATEGORIES_23:
        if category in c or c in category:
            return c
    # 常见别名
    aliases = {
        "编程": "编码开发", "开发": "编码开发", "写代码": "编码开发",
        "编程开发": "编码开发", "代码": "编码开发",
        "看视频": "视频/电影", "看片": "视频/电影", "视频": "视频/电影",
        "听音乐": "音乐/播客", "音乐": "音乐/播客",
        "聊天": "即时通讯", "通讯": "即时通讯",
        "上网": "网页浏览", "浏览": "网页浏览",
        "设计": "UI/UX设计",
    }
    return aliases.get(category, "其他/空闲")


class RecognizeService:
    """VLM 识别服务。"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._vlm_client: Optional[AIClient] = None
        self._prompt = _load_recognize_prompt()
        self._low_conf_threshold = config.settings.low_confidence_threshold

    def _get_vlm_client(self) -> AIClient:
        """懒加载 VLM 客户端。"""
        if self._vlm_client is None:
            self._vlm_client = AIClient(self._config.vlm)
        return self._vlm_client

    def recognize(self, screenshot: ScreenshotResult) -> Optional[RecognitionResult]:
        """识别单张截图。

        Args:
            screenshot: 截图结果（应为焦点屏）
        Returns:
            RecognitionResult 或 None（失败时）
        """
        image_bytes = image_to_bytes(screenshot.image, fmt="PNG")
        user_text = "识别这张屏幕截图的用户行为，输出 JSON。"
        try:
            resp = self._get_vlm_client().chat_with_image(
                system_prompt=self._prompt,
                user_text=user_text,
                image_bytes=image_bytes,
                max_tokens=2000,
                temperature=0.2,
            )
        except Exception as e:
            logger.error("VLM 调用失败: %s", e)
            return None

        # 解析 JSON
        data = _extract_json(resp.content)
        if data is None:
            # 重试一次，用更严格的提示
            logger.warning("首次 JSON 解析失败，重试")
            try:
                resp = self._get_vlm_client().chat_with_image(
                    system_prompt=self._prompt + "\n\n重要：只输出纯 JSON，不要任何其他文字。",
                    user_text=user_text,
                    image_bytes=image_bytes,
                    max_tokens=2000,
                    temperature=0.1,
                )
                data = _extract_json(resp.content)
            except Exception as e:
                logger.error("VLM 重试失败: %s", e)
                return None
            if data is None:
                logger.error("JSON 解析仍失败，原始输出: %s", resp.content[:200])
                return None

        category = _normalize_category(str(data.get("category", "其他/空闲")))
        sub_desc = str(data.get("sub_desc", "")).strip()
        object_name = str(data.get("object_name", "")).strip()
        activity = str(data.get("activity", "")).strip()
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        is_low = confidence < self._low_conf_threshold

        tokens = resp.total_tokens
        cost = tokens / 1000.0 * _VLM_COST_PER_1K

        return RecognitionResult(
            category=category, sub_desc=sub_desc, object_name=object_name,
            activity=activity, confidence=confidence, is_low_confidence=is_low,
            raw_response=resp.content, tokens_used=tokens, cost_estimate=cost,
        )

    def recognize_and_store(self, capture_id: int, screenshot: ScreenshotResult) -> Optional[int]:
        """识别截图并存储结果，返回 recognition_id。

        流程：识别 → 存 recognition → 更新 capture 状态 → 记录用量 → 异步向量化。
        """
        result = self.recognize(screenshot)
        if result is None:
            update_capture_recognition(capture_id, "failed")
            return None
        rid = insert_recognition(
            capture_id=capture_id,
            category=result.category,
            sub_desc=result.sub_desc,
            object_name=result.object_name,
            activity=result.activity,
            confidence=result.confidence,
            is_low_confidence=result.is_low_confidence,
            raw_response=result.raw_response,
            llm_tokens_used=result.tokens_used,
            llm_cost_estimate=result.cost_estimate,
        )
        update_capture_recognition(capture_id, "success", recognition_id=rid)
        record_usage("vlm", 1, result.tokens_used, result.cost_estimate)
        # 异步向量化（不阻塞识别主流程）
        text = " ".join(filter(None, [result.activity, result.sub_desc, result.object_name]))
        if text:
            threading.Thread(
                target=self._vectorize, args=(rid, text), daemon=True
            ).start()
        return rid

    def _vectorize(self, recognition_id: int, text: str) -> None:
        """对识别结果文本做向量化并入库。"""
        try:
            vec = get_embedder().encode_one(text)
            insert_recognition_vector(recognition_id, vec)
            record_usage("embedding", 1, 0, 0.0)
        except Exception as e:
            logger.warning("向量化失败(recognition_id=%s): %s", recognition_id, e)
