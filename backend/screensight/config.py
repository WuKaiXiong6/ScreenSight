# 文件路径：backend/screensight/config.py
# 文件作用：配置加载，分段解析 .env.local 区分 LLM/VLM 同名变量，加载可调参数
# 最后更新时间：2026-06-29-0115

"""配置加载模块。

解决 .env.local 中 LLM 段与 VLM 段变量同名（TALK2ESP_LLM_*）的冲突：
按注释行分块解析，将 LLM 段映射为 LLM_*，VLM 段映射为 VLM_*。
真实敏感值不打印、不入版本库。

路径策略：区分"只读资源根"与"用户可写数据根"，兼容源码运行与
PyInstaller 打包运行两种形态：
- 只读资源（prompts/前端 dist）：源码模式取项目源码位置，打包模式取 sys._MEIPASS
- 用户数据（数据库/截图/模型/.env.local）：源码模式取项目根，打包模式取 exe 所在目录
- 可通过环境变量 SCREENSIGHT_DATA_HOME 显式覆盖用户数据根
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包后的环境。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _resource_root() -> Path:
    """只读资源根目录。

    打包模式指向 PyInstaller 解压的临时目录 _MEIPASS；
    源码模式指向项目根（backend/.. 即仓库根）。
    """
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent.parent


def _user_data_root() -> Path:
    """用户可写数据根目录。

    优先级：环境变量 SCREENSIGHT_DATA_HOME > 打包模式 exe 所在目录 > 源码模式项目根。
    """
    override = os.environ.get("SCREENSIGHT_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


# 用户可写数据根（保留 PROJECT_ROOT 命名以兼容现有引用，但语义为"用户数据根"）
PROJECT_ROOT = _user_data_root()
# 只读资源根（prompts / 前端 dist 等随程序分发的资源）
RESOURCE_ROOT = _resource_root()

# 数据目录（用户可写）
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "screensight.db"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
MODEL_CACHE_DIR = DATA_DIR / "models"

# 只读资源目录（prompts / 前端 dist）
# 打包模式下 prompts 随 screensight 包被 PyInstaller 收集，仍位于 .../screensight/prompts
PROMPT_DIR = (
    RESOURCE_ROOT / "screensight" / "prompts"
    if _is_frozen()
    else Path(__file__).resolve().parent / "prompts"
)
# 后端目录：打包模式不存在真实 backend 目录，统一用 RESOURCE_ROOT 表示"程序资源根"
BACKEND_DIR = RESOURCE_ROOT if _is_frozen() else Path(__file__).resolve().parent.parent
# 前端 dist：打包模式下放在 RESOURCE_ROOT/frontend/dist；源码模式在 backend/.. /frontend/dist
FRONTEND_DIST = (
    RESOURCE_ROOT / "frontend" / "dist"
    if _is_frozen()
    else Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
)


@dataclass
class AIEndpointConfig:
    """单个 AI 端点配置（LLM 或 VLM）。"""
    provider: str = "openai_compat"
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class Settings:
    """可调运行参数（可通过界面修改，持久化到 settings 表）。"""
    capture_interval_active: int = 30      # 活跃截屏间隔（秒）
    capture_interval_idle: int = 300       # 空闲截屏间隔（秒）
    idle_threshold: int = 300              # 进入空闲的阈值（秒）
    low_confidence_threshold: float = 0.6  # 低置信度阈值
    archive_quality_near: int = 70         # 近期存档质量
    archive_scale_near: int = 50           # 近期存档缩放百分比
    archive_quality_mid: int = 40          # 中期存档质量
    archive_scale_mid: int = 30            # 中期存档缩放百分比
    retention_near_days: int = 30          # 近期保留天数
    retention_mid_days: int = 90           # 中期保留天数
    merge_gap_tolerance: int = 60          # 合并间隔容忍（秒）
    rag_top_k: int = 8                     # RAG 检索 top-K


@dataclass
class AppConfig:
    """应用全局配置。"""
    llm: AIEndpointConfig = field(default_factory=AIEndpointConfig)
    vlm: AIEndpointConfig = field(default_factory=AIEndpointConfig)
    settings: Settings = field(default_factory=Settings)
    host: str = "127.0.0.1"
    port: int = 8765
    # 本地 embedding 模型名（经 ModelScope 下载）
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_dim: int = 1024


# .env.local 中可能出现的键名后缀（兼容 TALK2ESP_LLM_* 与 LLM_* 两种前缀）
_KEY_SUFFIXES = ["PROVIDER", "BASE_URL", "API_KEY", "MODEL"]


def _parse_env_sections(env_path: Path) -> dict[str, dict[str, str]]:
    """按注释行分块解析 .env.local，返回 {"llm": {...}, "vlm": {...}}。

    解析规则：遇到含 "llm"（且不含 "vlm"）的注释行进入 llm 段；
    遇到含 "vlm" 的注释行进入 vlm 段。
    """
    sections: dict[str, dict[str, str]] = {"llm": {}, "vlm": {}}
    if not env_path.exists():
        return sections
    current: Optional[str] = None
    with env_path.open(encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith("#"):
                low = raw.lower()
                if "vlm" in low:
                    current = "vlm"
                elif "llm" in low:
                    current = "llm"
                continue
            if "=" not in raw or current is None:
                continue
            k, v = raw.split("=", 1)
            sections[current][k.strip()] = v.strip()
    return sections


def _build_endpoint(section: dict[str, str]) -> AIEndpointConfig:
    """从解析段构造端点配置，兼容 TALK2ESP_LLM_* 与 LLM_* 前缀。"""
    def pick(suffix: str) -> str:
        # 优先匹配段内任意前缀 + 后缀
        for k, v in section.items():
            if k.upper().endswith(suffix):
                return v
        return ""
    return AIEndpointConfig(
        provider=pick("PROVIDER") or "openai_compat",
        base_url=pick("BASE_URL"),
        api_key=pick("API_KEY"),
        model=pick("MODEL"),
    )


def _find_env_file() -> Optional[Path]:
    """查找 .env.local 或 .env 配置文件。"""
    for name in [".env.local", ".env"]:
        p = PROJECT_ROOT / name
        if p.exists():
            return p
    return None


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    """加载应用配置。

    Args:
        env_path: 指定 .env 文件路径；None 时自动查找 .env.local / .env
    Returns:
        AppConfig 实例，含 LLM/VLM 端点与默认可调参数
    """
    env_path = env_path or _find_env_file()
    config = AppConfig()
    if env_path is None:
        return config
    sections = _parse_env_sections(env_path)
    config.llm = _build_endpoint(sections["llm"])
    config.vlm = _build_endpoint(sections["vlm"])
    # host/port 可从环境变量覆盖
    config.host = os.environ.get("SCREENSIGHT_HOST", config.host)
    config.port = int(os.environ.get("SCREENSIGHT_PORT", config.port))
    return config


# 默认 23 类一级分类（与 PRD 一致）
CATEGORIES_23: list[str] = [
    "编码开发", "代码审查", "调试排错", "终端操作",
    "文档撰写", "文档阅读", "技术资料查阅", "笔记知识整理",
    "UI/UX设计", "图像编辑", "音视频制作",
    "即时通讯", "邮件处理", "视频会议",
    "网页浏览", "社交媒体",
    "视频/电影", "音乐/播客", "游戏",
    "在线学习",
    "文件管理", "系统工具", "其他/空闲",
]


def ensure_dirs() -> None:
    """确保运行时数据目录存在。"""
    for d in [DATA_DIR, SCREENSHOT_DIR, MODEL_CACHE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
