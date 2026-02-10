#!/usr/bin/env python3
"""
记忆 MCP 服务器 - 将记忆搜索和检索暴露为 MCP 工具。

此服务器提供：
    - memory_search: 对记忆文件的语义 + 关键词搜索
    - memory_get: 从记忆文件检索特定内容
    - memory_index: 触发记忆文件的重新索引

用法：
    python scripts/mcp_server.py

在 Claude Code 的 mcp.json 中配置：
    {
        "mcpServers": {
            "memory": {
                "command": "python",
                "args": ["/path/to/scripts/mcp_server.py"]
            }
        }
    }
"""

import json
import sys
import struct
import hashlib
import sqlite3
import math
import urllib.request
from pathlib import Path
from typing import Any
from datetime import datetime

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"

# 配置
from .config import get_cached_config
from .embedding_client import get_embedding

VECTOR_WEIGHT = 0.7
TEXT_WEIGHT = 0.3
DEFAULT_LIMIT = 6
MIN_SCORE = 0.25


# ============== 辅助函数 ==============

def get_db() -> sqlite3.Connection:
    """获取数据库连接。"""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def blob_to_embedding(blob: bytes) -> list[float]:
    """将二进制 blob 转换回嵌入列表。"""
    n = len(blob) // 4
    return list(struct.unpack(f'{n}f', blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量之间的余弦相似度。"""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def vector_search(conn: sqlite3.Connection, query_embedding: list[float], limit: int = 50) -> dict[int, float]:
    """通过向量相似度搜索。"""
    cursor = conn.execute("""
        SELECT e.chunk_id, e.embedding
        FROM embeddings e
        JOIN chunks c ON e.chunk_id = c.id
    """)

    scores = {}
    for row in cursor:
        chunk_embedding = blob_to_embedding(row['embedding'])
        similarity = cosine_similarity(query_embedding, chunk_embedding)
        scores[row['chunk_id']] = similarity

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_scores[:limit])


def text_search(conn: sqlite3.Connection, query: str, limit: int = 50) -> dict[int, float]:
    """通过 FTS5 关键词匹配搜索。"""
    fts_query = ' '.join(
        f'"{word}"' if any(c in word for c in '+-*()') else word
        for word in query.split()
    )

    try:
        cursor = conn.execute("""
            SELECT rowid, bm25(chunks_fts) as score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (fts_query, limit))

        rows = cursor.fetchall()
        if not rows:
            return {}

        scores = [(row['rowid'], -row['score']) for row in rows]
        max_score = max(s for _, s in scores) if scores else 1
        min_score = min(s for _, s in scores) if scores else 0
        range_score = max_score - min_score if max_score != min_score else 1

        return {
            chunk_id: (score - min_score) / range_score
            for chunk_id, score in scores
        }
    except sqlite3.OperationalError:
        return {}


def hybrid_search(conn: sqlite3.Connection, query: str, limit: int, min_score: float) -> list[dict]:
    """执行结合向量和关键词搜索的混合搜索。"""
    text_scores = text_search(conn, query)

    try:
        query_embedding = get_embedding(query)
        vector_scores = vector_search(conn, query_embedding)
    except Exception:
        vector_scores = {}

    all_chunk_ids = set(vector_scores.keys()) | set(text_scores.keys())
    combined_scores = {}

    for chunk_id in all_chunk_ids:
        v_score = vector_scores.get(chunk_id, 0)
        t_score = text_scores.get(chunk_id, 0)
        final_score = (VECTOR_WEIGHT * v_score) + (TEXT_WEIGHT * t_score)
        combined_scores[chunk_id] = (final_score, v_score, t_score)

    filtered = [
        (cid, scores) for cid, scores in combined_scores.items()
        if scores[0] >= min_score
    ]
    sorted_results = sorted(filtered, key=lambda x: x[1][0], reverse=True)[:limit]

    results = []
    for chunk_id, (final_score, v_score, t_score) in sorted_results:
        row = conn.execute(
            "SELECT file_path, line_start, line_end, content FROM chunks WHERE id = ?",
            (chunk_id,)
        ).fetchone()

        if row:
            results.append({
                "file_path": row['file_path'],
                "line_start": row['line_start'],
                "line_end": row['line_end'],
                "content": row['content'],
                "score": round(final_score, 3),
                "vector_score": round(v_score, 3),
                "text_score": round(t_score, 3)
            })

    return results


# ============== MCP 协议 ==============

def send_response(response: dict):
    """发送 JSON-RPC 响应。"""
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
    sys.stdout.flush()


def read_message() -> dict | None:
    """从 stdin 读取 JSON-RPC 消息。"""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line or line == '\r\n' or line == '\n':
            break
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get('Content-Length', 0))
    if content_length == 0:
        return None

    content = sys.stdin.read(content_length)
    return json.loads(content)


# ============== 工具实现 ==============

def tool_memory_search(arguments: dict) -> dict:
    """使用混合语义 + 关键词搜索记忆。"""
    query = arguments.get("query", "")
    max_results = arguments.get("maxResults", DEFAULT_LIMIT)
    min_score = arguments.get("minScore", MIN_SCORE)

    if not query:
        return {"error": "需要查询内容"}

    conn = get_db()
    if not conn:
        return {"error": "未找到记忆数据库。请先运行 index.py。"}

    try:
        results = hybrid_search(conn, query, max_results, min_score)
        conn.close()

        if not results:
            return {"message": "未找到匹配的记忆。", "results": []}

        return {"results": results}
    except Exception as e:
        return {"error": str(e)}


def tool_memory_get(arguments: dict) -> dict:
    """从记忆文件检索特定内容。"""
    path = arguments.get("path", "")
    from_line = arguments.get("from", 1)
    lines = arguments.get("lines", 50)

    if not path:
        return {"error": "需要路径"}

    file_path = PROJECT_DIR / path
    if not file_path.exists():
        return {"error": f"未找到文件：{path}"}

    try:
        all_lines = file_path.read_text().split('\n')
        start = max(0, from_line - 1)
        end = min(len(all_lines), start + lines)
        content = '\n'.join(all_lines[start:end])

        return {
            "path": path,
            "from": from_line,
            "to": end,
            "content": content
        }
    except Exception as e:
        return {"error": str(e)}


def tool_memory_index(arguments: dict) -> dict:
    """触发记忆文件的重新索引。"""
    import subprocess

    file_path = arguments.get("path")  # 可选的特定文件
    rebuild = arguments.get("rebuild", False)

    try:
        venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else sys.executable
        index_script = SCRIPT_DIR / "index.py"

        cmd = [python_cmd, str(index_script)]
        if rebuild:
            cmd.append("--rebuild")
        if file_path:
            cmd.append(file_path)

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR)

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        return {"error": str(e)}


def tool_memory_write(arguments: dict) -> dict:
    """将内容写入记忆文件。"""
    target = arguments.get("target", "daily")  # "daily" 或 "longterm"
    content = arguments.get("content", "")

    if not content:
        return {"error": "需要内容"}

    try:
        if target == "longterm":
            file_path = MEMORY_FILE
            # 在分隔线之前追加
            existing = file_path.read_text() if file_path.exists() else ""
            if "---" in existing:
                parts = existing.rsplit("---", 1)
                new_content = parts[0].rstrip() + "\n\n" + content + "\n\n---" + parts[1]
            else:
                new_content = existing.rstrip() + "\n\n" + content + "\n"
        else:
            # 每日日志
            today = datetime.now().strftime("%Y-%m-%d")
            file_path = MEMORY_DIR / f"{today}.md"

            if file_path.exists():
                existing = file_path.read_text()
                new_content = existing.rstrip() + "\n\n" + content + "\n"
            else:
                new_content = f"# {today}\n\n{content}\n"

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(new_content)

        return {
            "success": True,
            "path": str(file_path.relative_to(PROJECT_DIR)),
            "message": f"已写入 {file_path.name}"
        }
    except Exception as e:
        return {"error": str(e)}


# ============== MCP 处理器 ==============

TOOLS = [
    {
        "name": "memory_search",
        "description": "使用混合语义 + 关键词搜索记忆。返回带有文件路径、行号和相关性分数的排序结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询 - 可以是问题或关键词"
                },
                "maxResults": {
                    "type": "number",
                    "description": "返回的最大结果数（默认：6）",
                    "default": 6
                },
                "minScore": {
                    "type": "number",
                    "description": "最低相关性分数阈值（默认：0.25）",
                    "default": 0.25
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "memory_get",
        "description": "通过路径和行范围从记忆文件检索特定内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "记忆文件的相对路径（例如 'memory/2026-01-28.md'）"
                },
                "from": {
                    "type": "number",
                    "description": "起始行号（从 1 开始，默认：1）",
                    "default": 1
                },
                "lines": {
                    "type": "number",
                    "description": "要检索的行数（默认：50）",
                    "default": 50
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "memory_index",
        "description": "触发记忆文件的重新索引。在添加或修改记忆文件后运行此命令。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "可选：要索引的特定文件（如果省略则索引所有）"
                },
                "rebuild": {
                    "type": "boolean",
                    "description": "是否从头开始重建整个索引",
                    "default": False
                }
            }
        }
    },
    {
        "name": "memory_write",
        "description": "将内容写入记忆。使用 'daily' 表示会话笔记，'longterm' 表示重要的持久化事实。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["daily", "longterm"],
                    "description": "写入位置：'daily' 表示今日日志，'longterm' 表示 MEMORY.md",
                    "default": "daily"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容（Markdown 格式）"
                }
            },
            "required": ["content"]
        }
    }
]


def handle_initialize(params: dict) -> dict:
    """处理初始化请求。"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "memory",
            "version": "1.0.0"
        }
    }


def handle_tools_list(params: dict) -> dict:
    """处理 tools/list 请求。"""
    return {"tools": TOOLS}


def handle_tools_call(params: dict) -> dict:
    """处理 tools/call 请求。"""
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    handlers = {
        "memory_search": tool_memory_search,
        "memory_get": tool_memory_get,
        "memory_index": tool_memory_index,
        "memory_write": tool_memory_write
    }

    handler = handlers.get(name)
    if not handler:
        return {
            "content": [{"type": "text", "text": f"未知工具：{name}"}],
            "isError": True
        }

    result = handler(arguments)
    return {
        "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
        "isError": "error" in result
    }


def main():
    """主 MCP 服务器循环。"""
    while True:
        try:
            message = read_message()
            if message is None:
                break

            method = message.get("method", "")
            params = message.get("params", {})
            msg_id = message.get("id")

            result = None
            error = None

            if method == "initialize":
                result = handle_initialize(params)
            elif method == "notifications/initialized":
                continue  # 无需响应
            elif method == "tools/list":
                result = handle_tools_list(params)
            elif method == "tools/call":
                result = handle_tools_call(params)
            else:
                error = {"code": -32601, "message": f"未找到方法：{method}"}

            if msg_id is not None:
                response = {"jsonrpc": "2.0", "id": msg_id}
                if error:
                    response["error"] = error
                else:
                    response["result"] = result
                send_response(response)

        except Exception as e:
            if 'msg_id' in dir() and msg_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(e)}
                })


if __name__ == "__main__":
    main()
