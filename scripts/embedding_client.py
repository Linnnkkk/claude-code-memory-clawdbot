#!/usr/bin/env python3
"""
通用嵌入客户端 - 支持多种嵌入 API 提供商。

支持：
    - Ollama API
    - OpenAI 兼容 API
"""

import json
import urllib.request
from typing import Any
from .config import get_cached_config


class EmbeddingClient:
    """统一的嵌入 API 客户端。"""

    def __init__(self):
        """初始化客户端，加载配置。"""
        self.config = get_cached_config()
        self.provider = self.config.get("provider", "ollama")
        self.base_url = self.config["base_url"]
        self.model = self.config["model"]
        self.api_key = self.config.get("api_key", "")

    def get_embedding(self, text: str) -> list[float]:
        """
        获取文本的嵌入向量。

        参数：
            text: 要嵌入的文本

        返回：
            嵌入向量（浮点数列表）

        抛出：
            URLError: API 请求失败
            ValueError: API 响应格式错误
        """
        if self.provider == "ollama":
            return self._get_ollama_embedding(text)
        else:
            return self._get_openai_compatible_embedding(text)

    def _get_ollama_embedding(self, text: str) -> list[float]:
        """
        从 Ollama API 获取嵌入。

        Ollama API 格式：
            请求：{"model": "...", "prompt": "..."}
            响应：{"embedding": [...]}
        """
        data = json.dumps({
            "model": self.model,
            "prompt": text
        }).encode('utf-8')

        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            embedding = result.get("embedding")

            if not embedding or not isinstance(embedding, list):
                raise ValueError(f"Ollama API 响应格式错误：{result}")

            return embedding

    def _get_openai_compatible_embedding(self, text: str) -> list[float]:
        """
        从 OpenAI 兼容 API 获取嵌入。

        OpenAI API 格式：
            请求：{"model": "...", "input": "..."}
            响应：{"data": [{"embedding": [...]}]}

        支持：
            - OpenAI 官方 API
            - 本地 Ollama（使用 OpenAI 兼容模式）
            - 其他兼容 OpenAI 的服务
        """
        data = json.dumps({
            "model": self.model,
            "input": text
        }).encode('utf-8')

        headers = {"Content-Type": "application/json"}

        # 如果有 API Key，添加 Authorization header
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))

            data_list = result.get("data", [])
            if not data_list:
                raise ValueError(f"API 响应中没有数据：{result}")

            embedding = data_list[0].get("embedding")

            if not embedding or not isinstance(embedding, list):
                raise ValueError(f"API 响应格式错误：{result}")

            return embedding


# 全局客户端实例
_client_instance: EmbeddingClient | None = None


def get_client() -> EmbeddingClient:
    """
    获取全局嵌入客户端实例。

    返回：
        EmbeddingClient 实例
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = EmbeddingClient()
    return _client_instance


def get_embedding(text: str) -> list[float]:
    """
    获取文本嵌入的便捷函数。

    参数：
        text: 要嵌入的文本

    返回：
        嵌入向量
    """
    return get_client().get_embedding(text)


if __name__ == "__main__":
    # 测试客户端
    import sys
    client = get_client()

    print(f"配置：")
    print(f"  Provider: {client.provider}")
    print(f"  Base URL: {client.base_url}")
    print(f"  Model: {client.model}")
    print(f"  API Key: {'已设置' if client.api_key else '未设置'}")
    print()

    if len(sys.argv) > 1:
        test_text = ' '.join(sys.argv[1:])
    else:
        test_text = "测试文本"

    print(f"测试嵌入：{test_text}")
    try:
        embedding = client.get_embedding(test_text)
        print(f"嵌入维度：{len(embedding)}")
        print(f"前 10 个值：{embedding[:10]}")
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
