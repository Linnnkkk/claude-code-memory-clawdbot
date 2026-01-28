#!/usr/bin/env python3
"""
Memory search - hybrid semantic + keyword search over memory files.

Usage:
    python scripts/search.py "what database did we choose"
    python scripts/search.py "API design decisions" --limit 10
    python scripts/search.py "postgres" --keyword-only
"""

import sqlite3
import json
import struct
import sys
import math
import urllib.request
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Configuration
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
VECTOR_WEIGHT = 0.7  # Weight for vector similarity
TEXT_WEIGHT = 0.3    # Weight for BM25 text search
DEFAULT_LIMIT = 6
MIN_SCORE = 0.25

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"


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
    """Get database connection."""
    if not DB_PATH.exists():
        print("Error: Database not found. Run index.py first.", file=sys.stderr)
        sys.exit(1)

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

    with urllib.request.urlopen(req) as response:
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
    """
    Search by vector similarity.
    Returns dict of chunk_id -> similarity score.
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

    # Return top N by similarity
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_scores[:limit])


def text_search(conn: sqlite3.Connection, query: str, limit: int = 50) -> dict[int, float]:
    """
    Search by FTS5 keyword matching.
    Returns dict of chunk_id -> BM25 score (normalized to 0-1).
    """
    # FTS5 query - escape special characters
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

        # BM25 scores are negative, more negative = better match
        # Normalize to 0-1 range
        scores = [(row['rowid'], -row['score']) for row in rows]
        max_score = max(s for _, s in scores) if scores else 1
        min_score = min(s for _, s in scores) if scores else 0
        range_score = max_score - min_score if max_score != min_score else 1

        return {
            chunk_id: (score - min_score) / range_score
            for chunk_id, score in scores
        }
    except sqlite3.OperationalError:
        # FTS query failed (e.g., syntax error)
        return {}


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = DEFAULT_LIMIT,
    min_score: float = MIN_SCORE,
    keyword_only: bool = False
) -> list[SearchResult]:
    """
    Perform hybrid search combining vector and keyword search.
    """
    # Get text search scores
    text_scores = text_search(conn, query)

    # Get vector search scores (unless keyword-only)
    if keyword_only:
        vector_scores = {}
    else:
        query_embedding = get_embedding(query)
        vector_scores = vector_search(conn, query_embedding)

    # Combine scores
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

    # Filter and sort
    filtered = [
        (cid, scores) for cid, scores in combined_scores.items()
        if scores[0] >= min_score
    ]
    sorted_results = sorted(filtered, key=lambda x: x[1][0], reverse=True)[:limit]

    # Fetch chunk details
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
    """Format search results for display."""
    if not results:
        return "No matching memories found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"## Result {i} (score: {r.score:.2f})")
        lines.append(f"**File:** {r.file_path}:{r.line_start}-{r.line_end}")
        if verbose:
            lines.append(f"**Scores:** vector={r.vector_score:.2f}, text={r.text_score:.2f}")
        lines.append("")
        # Truncate content if too long
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

    parser = argparse.ArgumentParser(description="Search memory files")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", "-n", type=int, default=DEFAULT_LIMIT, help="Max results")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE, help="Minimum score threshold")
    parser.add_argument("--keyword-only", "-k", action="store_true", help="Use only keyword search")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed scores")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

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
        print(f"Search error: {e}", file=sys.stderr)
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
