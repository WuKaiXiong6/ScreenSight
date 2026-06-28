# 文件路径：backend/screensight/infra/ai_client.py
# 文件作用：OpenAI 兼容协议客户端封装，统一处理 LLM/VLM 调用与推理模型特性
# 最后更新时间：2026-06-28-1949

"""AI 客户端封装。

适配两类推理模型：
- glm-5.2（LLM，火山方舟）：max_tokens 需 >=2000，输出在 content，推理在 reasoning_content
- mimo-v2.5（VLM，小米）：同上，支持 image_url 多模态输入

关键点：推理模型需预留足够 max_tokens 给推理过程，否则 content 为空。
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from ..config import AIEndpointConfig


# 推理模型建议的最小 max_tokens（预留推理预算）
MIN_MAX_TOKENS_FOR_REASONING = 2000


@dataclass
class AIResponse:
    """AI 调用结果。"""
    content: str               # 最终输出文本（已剥离推理过程）
    raw_content: str           # 原始 content
    reasoning: str             # 推理过程（reasoning_content，可能为空）
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int
    elapsed_seconds: float


class AIClient:
    """OpenAI 兼容协议客户端，支持文本与多模态（图片）调用。"""

    def __init__(self, endpoint: AIEndpointConfig, timeout: float = 120.0):
        self._endpoint = endpoint
        self._client = OpenAI(
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
            timeout=timeout,
        )

    @property
    def model(self) -> str:
        return self._endpoint.model

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = MIN_MAX_TOKENS_FOR_REASONING,
        temperature: float = 0.2,
        response_format: Optional[dict] = None,
    ) -> AIResponse:
        """文本对话调用。

        Args:
            messages: OpenAI 消息格式
            max_tokens: 最大 token 数（推理模型需 >=2000）
            temperature: 采样温度
            response_format: 可选，强制 JSON 输出 {"type": "json_object"}
        """
        kwargs: dict[str, Any] = {
            "model": self._endpoint.model,
            "messages": messages,
            "max_tokens": max(MIN_MAX_TOKENS_FOR_REASONING, max_tokens),
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        t0 = time.time()
        resp = self._client.chat.completions.create(**kwargs)
        elapsed = time.time() - t0
        return _build_response(resp, elapsed)

    def chat_with_image(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        image_media_type: str = "image/png",
        max_tokens: int = MIN_MAX_TOKENS_FOR_REASONING,
        temperature: float = 0.2,
    ) -> AIResponse:
        """多模态调用：发送文本 + 图片。

        Args:
            system_prompt: 系统提示词
            user_text: 用户文本指令
            image_bytes: 图片二进制数据
            image_media_type: 图片 MIME 类型
        """
        img_b64 = base64.b64encode(image_bytes).decode("ascii")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {
                    "url": f"data:{image_media_type};base64,{img_b64}",
                }},
            ]},
        ]
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature)

    def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """调用 embedding 端点。

        注意：当前配置的 LLM/VLM 端点均不支持 embedding，此方法仅作兼容预留，
        实际向量化使用本地 Embedder（见 embedder.py）。
        """
        resp = self._client.embeddings.create(
            model=model or self._endpoint.model,
            input=text,
        )
        return resp.data[0].embedding


def _build_response(resp: Any, elapsed: float) -> AIResponse:
    """从 SDK 响应构造 AIResponse，兼容推理模型的 reasoning_content 字段。"""
    choice = resp.choices[0]
    msg = choice.message
    content = getattr(msg, "content", None) or ""
    reasoning = getattr(msg, "reasoning_content", None) or ""
    usage = resp.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or 0
    # 推理 token 在 completion_tokens_details.reasoning_tokens
    details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = 0
    if details is not None:
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0
    return AIResponse(
        content=content,
        raw_content=content,
        reasoning=reasoning,
        finish_reason=choice.finish_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        reasoning_tokens=reasoning_tokens,
        elapsed_seconds=elapsed,
    )


def encode_image_file(path: Path | str) -> bytes:
    """读取图片文件为二进制。"""
    with open(path, "rb") as f:
        return f.read()
