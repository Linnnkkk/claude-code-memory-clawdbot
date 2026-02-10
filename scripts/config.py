#!/usr/bin/env python3
"""
配置加载模块 - 加载和验证嵌入 API 配置。

支持 Ollama 和 OpenAI 兼容的 API。
"""

import json
from pathlib import Path
from typing import Any

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / ".config" / "embedding.json"


# 默认配置（向后兼容）
DEFAULT_CONFIG = {
    "provider": "ollama",
    "base_url": "http://localhost:11434/api/embeddings",
    "model": "nomic-embed-text"
}


def load_config() -> dict[str, Any]:
    """
    加载配置文件。如果不存在，返回默认配置。

    返回：
        包含 provider, base_url, model, (可选) api_key 的字典
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 验证必需字段
        required_fields = ["provider", "base_url", "model"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"配置文件缺少必需字段：{field}")

        # 如果没有 api_key，设置为空字符串
        if "api_key" not in config:
            config["api_key"] = ""

        return config
    except (json.JSONDecodeError, ValueError) as e:
        print(f"配置文件错误：{e}，使用默认配置", file=__import__('sys').stderr)
        return DEFAULT_CONFIG.copy()


def get_config() -> dict[str, Any]:
    """
    获取配置（别名）。

    这是 load_config() 的别名，用于保持向后兼容。
    """
    return load_config()


def save_config(config: dict[str, Any]) -> None:
    """
    保存配置文件。

    参数：
        config: 配置字典
    """
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# 全局配置缓存
_config_cache: dict[str, Any] | None = None


def get_cached_config() -> dict[str, Any]:
    """
    获取缓存的配置。只在首次调用时加载。

    返回：
        配置字典
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache
