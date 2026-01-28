#!/usr/bin/env python3
"""
Memory indexer - chunks markdown files and stores embeddings in SQLite.

Usage:
    python scripts/index.py                    # Index all memory files
    python scripts/index.py memory/2026-01-28.md  # Index specific file
    python scripts/index.py --rebuild          # Rebuild entire index
"""

import sqlite3
import hashlib
import json
import struct
import sys
import os
import urllib.request
from pathlib import Path
from typing import Iterator

# Configuration
CHUNK_SIZE = 400  # Target tokens per chunk (approximated as words * 1.3)
CHUNK_OVERLAP = 80  # Overlap tokens between chunks
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"


def get_db() -> sqlite3.Connection:
    """Get database connection, creating schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Initialize schema
    schema_path = SCRIPT_DIR / "schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text())

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


def embedding_to_blob(embedding: list[float]) -> bytes:
    """Convert embedding list to binary blob for SQLite storage."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def blob_to_embedding(blob: bytes) -> list[float]:
    """Convert binary blob back to embedding list."""
    n = len(blob) // 4  # 4 bytes per float
    return list(struct.unpack(f'{n}f', blob))


def chunk_text(text: str, file_path: str) -> Iterator[dict]:
    """
    Split text into overlapping chunks.
    Returns dicts with content, line_start, line_end.
    """
    lines = text.split('\n')

    # Approximate tokens as words * 1.3
    def estimate_tokens(s: str) -> int:
        return int(len(s.split()) * 1.3)

    chunk_lines = []
    chunk_start = 0
    current_tokens = 0

    for i, line in enumerate(lines):
        line_tokens = estimate_tokens(line)

        if current_tokens + line_tokens > CHUNK_SIZE and chunk_lines:
            # Yield current chunk
            content = '\n'.join(chunk_lines)
            yield {
                'content': content,
                'line_start': chunk_start + 1,  # 1-indexed
                'line_end': chunk_start + len(chunk_lines),
                'file_path': file_path
            }

            # Calculate overlap - keep last N tokens worth of lines
            overlap_lines = []
            overlap_tokens = 0
            for prev_line in reversed(chunk_lines):
                lt = estimate_tokens(prev_line)
                if overlap_tokens + lt > CHUNK_OVERLAP:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_tokens += lt

            # Start new chunk with overlap
            chunk_lines = overlap_lines + [line]
            chunk_start = i - len(overlap_lines)
            current_tokens = overlap_tokens + line_tokens
        else:
            chunk_lines.append(line)
            current_tokens += line_tokens

    # Yield final chunk
    if chunk_lines:
        content = '\n'.join(chunk_lines)
        yield {
            'content': content,
            'line_start': chunk_start + 1,
            'line_end': chunk_start + len(chunk_lines),
            'file_path': file_path
        }


def content_hash(content: str) -> str:
    """Generate hash of content for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def index_file(conn: sqlite3.Connection, file_path: Path, force: bool = False):
    """Index a single file."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    rel_path = str(file_path.relative_to(PROJECT_DIR))
    text = file_path.read_text()

    if force:
        # Delete existing chunks for this file
        cursor = conn.execute(
            "SELECT id FROM chunks WHERE file_path = ?",
            (rel_path,)
        )
        for row in cursor:
            conn.execute("DELETE FROM embeddings WHERE chunk_id = ?", (row['id'],))
        conn.execute("DELETE FROM chunks WHERE file_path = ?", (rel_path,))

    chunks_added = 0
    chunks_skipped = 0

    for chunk in chunk_text(text, rel_path):
        c_hash = content_hash(chunk['content'])

        # Check if chunk already exists
        existing = conn.execute(
            "SELECT id FROM chunks WHERE file_path = ? AND line_start = ? AND content_hash = ?",
            (rel_path, chunk['line_start'], c_hash)
        ).fetchone()

        if existing:
            chunks_skipped += 1
            continue

        # Insert chunk
        cursor = conn.execute(
            """INSERT INTO chunks (file_path, line_start, line_end, content, content_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (rel_path, chunk['line_start'], chunk['line_end'], chunk['content'], c_hash)
        )
        chunk_id = cursor.lastrowid

        # Get and store embedding
        try:
            embedding = get_embedding(chunk['content'])
            blob = embedding_to_blob(embedding)
            conn.execute(
                "INSERT INTO embeddings (chunk_id, embedding, model) VALUES (?, ?, ?)",
                (chunk_id, blob, EMBEDDING_MODEL)
            )
            chunks_added += 1
        except Exception as e:
            print(f"  Error embedding chunk: {e}")
            # Remove the chunk if embedding failed
            conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))

    conn.commit()
    print(f"Indexed {file_path.name}: {chunks_added} added, {chunks_skipped} skipped")


def index_all(conn: sqlite3.Connection, force: bool = False):
    """Index all markdown files in memory directory."""
    # Index MEMORY.md if it exists
    memory_file = PROJECT_DIR / "MEMORY.md"
    if memory_file.exists():
        index_file(conn, memory_file, force)

    # Index all files in memory/
    if MEMORY_DIR.exists():
        for md_file in sorted(MEMORY_DIR.glob("*.md")):
            index_file(conn, md_file, force)


def main():
    args = sys.argv[1:]
    force = "--rebuild" in args
    args = [a for a in args if a != "--rebuild"]

    conn = get_db()

    if args:
        # Index specific files
        for path in args:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = PROJECT_DIR / path
            index_file(conn, file_path, force)
    else:
        # Index all
        index_all(conn, force)

    # Show stats
    count = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()['c']
    print(f"\nTotal chunks in database: {count}")

    conn.close()


if __name__ == "__main__":
    main()
