#!/usr/bin/env python3
"""
Memory MCP Server - Exposes memory search and retrieval as MCP tools.

This server provides:
    - memory_search: Semantic + keyword search over memory files
    - memory_get: Retrieve specific content from memory files
    - memory_index: Trigger re-indexing of memory files

Usage:
    python scripts/mcp_server.py

Configure in Claude Code's mcp.json:
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

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"

# Configuration
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
VECTOR_WEIGHT = 0.7
TEXT_WEIGHT = 0.3
DEFAULT_LIMIT = 6
MIN_SCORE = 0.25


# ============== Helper Functions ==============

def get_db() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_embedding(text: str) -> list[float]:
    """Get embedding from Ollama."""
    data = json.dumps({
        "model": EMBEDDING_MODEL,
        "prompt": text
    }).encode('utf-8')

    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result["embedding"]


def blob_to_embedding(blob: bytes) -> list[float]:
    """Convert binary blob back to embedding list."""
    n = len(blob) // 4
    return list(struct.unpack(f'{n}f', blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def vector_search(conn: sqlite3.Connection, query_embedding: list[float], limit: int = 50) -> dict[int, float]:
    """Search by vector similarity."""
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
    """Search by FTS5 keyword matching."""
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
    """Perform hybrid search combining vector and keyword search."""
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


# ============== MCP Protocol ==============

def send_response(response: dict):
    """Send a JSON-RPC response."""
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
    sys.stdout.flush()


def read_message() -> dict | None:
    """Read a JSON-RPC message from stdin."""
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


# ============== Tool Implementations ==============

def tool_memory_search(arguments: dict) -> dict:
    """Search memories using hybrid semantic + keyword search."""
    query = arguments.get("query", "")
    max_results = arguments.get("maxResults", DEFAULT_LIMIT)
    min_score = arguments.get("minScore", MIN_SCORE)

    if not query:
        return {"error": "Query is required"}

    conn = get_db()
    if not conn:
        return {"error": "Memory database not found. Run index.py first."}

    try:
        results = hybrid_search(conn, query, max_results, min_score)
        conn.close()

        if not results:
            return {"message": "No matching memories found.", "results": []}

        return {"results": results}
    except Exception as e:
        return {"error": str(e)}


def tool_memory_get(arguments: dict) -> dict:
    """Retrieve specific content from a memory file."""
    path = arguments.get("path", "")
    from_line = arguments.get("from", 1)
    lines = arguments.get("lines", 50)

    if not path:
        return {"error": "Path is required"}

    file_path = PROJECT_DIR / path
    if not file_path.exists():
        return {"error": f"File not found: {path}"}

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
    """Trigger re-indexing of memory files."""
    import subprocess

    file_path = arguments.get("path")  # Optional specific file
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
    """Write content to a memory file."""
    target = arguments.get("target", "daily")  # "daily" or "longterm"
    content = arguments.get("content", "")

    if not content:
        return {"error": "Content is required"}

    try:
        if target == "longterm":
            file_path = MEMORY_FILE
            # Append before the separator line
            existing = file_path.read_text() if file_path.exists() else ""
            if "---" in existing:
                parts = existing.rsplit("---", 1)
                new_content = parts[0].rstrip() + "\n\n" + content + "\n\n---" + parts[1]
            else:
                new_content = existing.rstrip() + "\n\n" + content + "\n"
        else:
            # Daily log
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
            "message": f"Written to {file_path.name}"
        }
    except Exception as e:
        return {"error": str(e)}


# ============== MCP Handlers ==============

TOOLS = [
    {
        "name": "memory_search",
        "description": "Search memories using hybrid semantic + keyword search. Returns ranked results with file paths, line numbers, and relevance scores.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query - can be a question or keywords"
                },
                "maxResults": {
                    "type": "number",
                    "description": "Maximum number of results to return (default: 6)",
                    "default": 6
                },
                "minScore": {
                    "type": "number",
                    "description": "Minimum relevance score threshold (default: 0.25)",
                    "default": 0.25
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "memory_get",
        "description": "Retrieve specific content from a memory file by path and line range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the memory file (e.g., 'memory/2026-01-28.md')"
                },
                "from": {
                    "type": "number",
                    "description": "Starting line number (1-indexed, default: 1)",
                    "default": 1
                },
                "lines": {
                    "type": "number",
                    "description": "Number of lines to retrieve (default: 50)",
                    "default": 50
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "memory_index",
        "description": "Trigger re-indexing of memory files. Run this after adding or modifying memory files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional: specific file to index (indexes all if omitted)"
                },
                "rebuild": {
                    "type": "boolean",
                    "description": "Whether to rebuild the entire index from scratch",
                    "default": False
                }
            }
        }
    },
    {
        "name": "memory_write",
        "description": "Write content to memory. Use 'daily' for session notes, 'longterm' for important persistent facts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["daily", "longterm"],
                    "description": "Where to write: 'daily' for today's log, 'longterm' for MEMORY.md",
                    "default": "daily"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (markdown format)"
                }
            },
            "required": ["content"]
        }
    }
]


def handle_initialize(params: dict) -> dict:
    """Handle initialize request."""
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
    """Handle tools/list request."""
    return {"tools": TOOLS}


def handle_tools_call(params: dict) -> dict:
    """Handle tools/call request."""
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
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True
        }

    result = handler(arguments)
    return {
        "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
        "isError": "error" in result
    }


def main():
    """Main MCP server loop."""
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
                continue  # No response needed
            elif method == "tools/list":
                result = handle_tools_list(params)
            elif method == "tools/call":
                result = handle_tools_call(params)
            else:
                error = {"code": -32601, "message": f"Method not found: {method}"}

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
