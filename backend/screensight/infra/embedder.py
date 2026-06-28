# 文件路径：backend/screensight/infra/embedder.py
# 文件作用：本地 embedding 向量化，使用 bge-large-zh-v1.5 模型
# 最后更新时间：2026-06-28-1949

"""本地 embedding 引擎。

使用 BAAI/bge-large-zh-v1.5（1024 维，中文专精）做向量化，数据不出本机。
模型经 ModelScope 下载到 data/models 缓存，首次使用自动下载。
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from ..config import MODEL_CACHE_DIR

logger = logging.getLogger(__name__)

# 模型在 ModelScope 上的仓库 ID
MODEL_REPO = "BAAI/bge-large-zh-v1.5"
EMBEDDING_DIM = 1024


class Embedder:
    """本地向量化引擎，懒加载模型，线程安全。"""

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        """懒加载模型，首次调用时加载。"""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer
            path = self._resolve_model_path()
            logger.info("加载 embedding 模型: %s", path)
            self._model = SentenceTransformer(path)
            logger.info(
                "embedding 模型加载完成，维度=%s",
                self._model.get_sentence_embedding_dimension(),
            )

    def _resolve_model_path(self) -> str:
        """解析模型路径：优先本地缓存，其次下载。"""
        if self._model_path:
            return self._model_path
        # ModelScope 下载时会将点号转为下划线（bge-large-zh-v1___5）
        cache_dir = MODEL_CACHE_DIR
        # 查找已下载的模型目录
        repo_dir = cache_dir / "BAAI"
        if repo_dir.exists():
            for d in repo_dir.iterdir():
                if d.is_dir() and "bge-large-zh" in d.name.lower():
                    return str(d)
        # 未找到则触发下载
        return self._download_model()

    def _download_model(self) -> str:
        """从 ModelScope 下载模型到本地缓存。"""
        from modelscope import snapshot_download
        logger.info("从 ModelScope 下载 embedding 模型 %s ...", MODEL_REPO)
        path = snapshot_download(MODEL_REPO, cache_dir=str(MODEL_CACHE_DIR))
        logger.info("模型下载完成: %s", path)
        return path

    def encode(self, texts: str | list[str], normalize: bool = True):
        """对文本做向量化。

        Args:
            texts: 单条文本或文本列表
            normalize: 是否 L2 归一化（用于余弦相似度）
        Returns:
            单条文本返回一维 ndarray；列表返回二维 ndarray
        """
        self._ensure_model()
        return self._model.encode(texts, normalize_embeddings=normalize)

    def encode_one(self, text: str, normalize: bool = True) -> list[float]:
        """对单条文本做向量化，返回 list[float]。"""
        self._ensure_model()
        vec = self._model.encode([text], normalize_embeddings=normalize)
        return vec[0].tolist()


# 全局单例（懒加载，避免未使用时占用内存）
_global_embedder: Optional[Embedder] = None
_global_lock = threading.Lock()


def get_embedder() -> Embedder:
    """获取全局 Embedder 单例。"""
    global _global_embedder
    if _global_embedder is None:
        with _global_lock:
            if _global_embedder is None:
                _global_embedder = Embedder()
    return _global_embedder
