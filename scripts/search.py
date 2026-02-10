#!/usr/bin/env python3
"""
记忆搜索 - 对记忆文件进行混合语义 + 关键词搜索。

用法：
    python scripts/search.py "我们选择了什么数据库"
    python scripts/search.py "API 设计决策" --limit 10
    python scripts/search.py "postgres" --keyword-only
"""

import sqlite3
import json
import struct
import sys
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"

# 配置
from .config import get_cached_config
from .embedding_client import get_embedding

VECTOR_WEIGHT = 0.7  # 向量相似度权重
TEXT_WEIGHT = 0.3    # BM25 文本搜索权重
DEFAULT_LIMIT = 6
MIN_SCORE = 0.25


@dataclass
class SearchResult:
    file_path: str
    line_start: int
    line_end: int
    content: str
    score: float
    vector_score: float
    text_score: float


def get_db() -> sqlite3.Connection:
    """获取数据库连接。"""
    if not DB_PATH.exists():
        print("错误：未找到数据库。请先运行 index.py。", file=sys.stderr)
        sys.exit(1)

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
    """
    通过向量相似度搜索。
    返回 chunk_id -> 相似度分数的字典。
    """
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

    # 按相似度返回前 N 个
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_scores[:limit])


def text_search(conn: sqlite3.Connection, query: str, limit: int = 50) -> dict[int, float]:
    """
    通过 FTS5 关键词匹配搜索。
    返回 chunk_id -> BM25 分数（归一化到 0-1）的字典。
    """
    # FTS5 查询 - 转义特殊字符
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

        # BM25 分数是负数，越负表示匹配越好
        # 归一化到 0-1 范围
        scores = [(row['rowid'], -row['score']) for row in rows]
        max_score = max(s for _, s in scores) if scores else 1
        min_score = min(s for _, s in scores) if scores else 0
        range_score = max_score - min_score if max_score != min_score else 1

        return {
            chunk_id: (score - min_score) / range_score
            for chunk_id, score in scores
        }
    except sqlite3.OperationalError:
        # FTS 查询失败（例如，语法错误）
        return {}


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = DEFAULT_LIMIT,
    min_score: float = MIN_SCORE,
    keyword_only: bool = False
) -> list[SearchResult]:
    """
    执行结合向量和关键词搜索的混合搜索。
    """
    # 获取文本搜索分数
    text_scores = text_search(conn, query)

    # 获取向量搜索分数（除非仅限关键词）
    if keyword_only:
        vector_scores = {}
    else:
        query_embedding = get_embedding(query)
        vector_scores = vector_search(conn, query_embedding)

    # 合并分数
    all_chunk_ids = set(vector_scores.keys()) | set(text_scores.keys())
    combined_scores = {}

    for chunk_id in all_chunk_ids:
        v_score = vector_scores.get(chunk_id, 0)
        t_score = text_scores.get(chunk_id, 0)

        if keyword_only:
            final_score = t_score
        else:
            final_score = (VECTOR_WEIGHT * v_score) + (TEXT_WEIGHT * t_score)

        combined_scores[chunk_id] = (final_score, v_score, t_score)

    # 过滤和排序
    filtered = [
        (cid, scores) for cid, scores in combined_scores.items()
        if scores[0] >= min_score
    ]
    sorted_results = sorted(filtered, key=lambda x: x[1][0], reverse=True)[:limit]

    # 获取块详情
    results = []
    for chunk_id, (final_score, v_score, t_score) in sorted_results:
        row = conn.execute(
            "SELECT file_path, line_start, line_end, content FROM chunks WHERE id = ?",
            (chunk_id,)
        ).fetchone()

        if row:
            results.append(SearchResult(
                file_path=row['file_path'],
                line_start=row['line_start'],
                line_end=row['line_end'],
                content=row['content'],
                score=final_score,
                vector_score=v_score,
                text_score=t_score
            ))

    return results


def format_results(results: list[SearchResult], verbose: bool = False) -> str:
    """格式化搜索结果以供显示。"""
    if not results:
        return "未找到匹配的记忆。"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"## 结果 {i}（分数：{r.score:.2f}）")
        lines.append(f"**文件：** {r.file_path}:{r.line_start}-{r.line_end}")
        if verbose:
            lines.append(f"**分数：** 向量={r.vector_score:.2f}, 文本={r.text_score:.2f}")
        lines.append("")
        # 如果内容太长则截断
        content = r.content
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="搜索记忆文件")
    parser.add_argument("query", help="搜索查询")
    parser.add_argument("--limit", "-n", type=int, default=DEFAULT_LIMIT, help="最大结果数")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE, help="最低分数阈值")
    parser.add_argument("--keyword-only", "-k", action="store_true", help="仅使用关键词搜索")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细分数")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    # 显示配置信息
    config = get_cached_config()
    print(f"使用配置：Provider={config.get('provider', 'ollama')}, Model={config['model']}\n")

    conn = get_db()

    try:
        results = hybrid_search(
            conn,
            args.query,
            limit=args.limit,
            min_score=args.min_score,
            keyword_only=args.keyword_only
        )
    except Exception as e:
        print(f"搜索错误：{e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        output = [
            {
                "file_path": r.file_path,
                "line_start": r.line_start,
                "line_end": r.line_end,
                "content": r.content,
                "score": r.score,
                "vector_score": r.vector_score,
                "text_score": r.text_score
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        print(format_results(results, verbose=args.verbose))

    conn.close()


if __name__ == "__main__":
    main()
