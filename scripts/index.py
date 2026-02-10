#!/usr/bin/env python3
"""
记忆索引器 - 将 Markdown 文件分块并将嵌入存储在 SQLite 中。

用法：
    python scripts/index.py                    # 索引所有记忆文件
    python scripts/index.py memory/2026-01-28.md  # 索引特定文件
    python scripts/index.py --rebuild          # 重建整个索引
"""

import sqlite3
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Iterator

# 配置
CHUNK_SIZE = 400  # 每个块的目标 token 数（近似为单词数 * 1.3）
CHUNK_OVERLAP = 80  # 块之间的重叠 token 数

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"

# 导入配置和嵌入客户端
from .config import get_cached_config
from .embedding_client import get_embedding


def get_db() -> sqlite3.Connection:
    """获取数据库连接，必要时创建架构。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 初始化架构
    schema_path = SCRIPT_DIR / "schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text())

    return conn


def embedding_to_blob(embedding: list[float]) -> bytes:
    """将嵌入列表转换为二进制 blob 以便 SQLite 存储。"""
    return struct.pack(f'{len(embedding)}f', *embedding)


def blob_to_embedding(blob: bytes) -> list[float]:
    """将二进制 blob 转换回嵌入列表。"""
    n = len(blob) // 4  # 每个浮点数 4 字节
    return list(struct.unpack(f'{n}f', blob))


def chunk_text(text: str, file_path: str) -> Iterator[dict]:
    """
    将文本分割成重叠的块。
    返回包含 content、line_start、line_end 的字典。
    """
    lines = text.split('\n')

    # 近似 token 为单词数 * 1.3
    def estimate_tokens(s: str) -> int:
        return int(len(s.split()) * 1.3)

    chunk_lines = []
    chunk_start = 0
    current_tokens = 0

    for i, line in enumerate(lines):
        line_tokens = estimate_tokens(line)

        if current_tokens + line_tokens > CHUNK_SIZE and chunk_lines:
            # 输出当前块
            content = '\n'.join(chunk_lines)
            yield {
                'content': content,
                'line_start': chunk_start + 1,  # 从 1 开始索引
                'line_end': chunk_start + len(chunk_lines),
                'file_path': file_path
            }

            # 计算重叠 - 保留最后 N 个 token 值的行
            overlap_lines = []
            overlap_tokens = 0
            for prev_line in reversed(chunk_lines):
                lt = estimate_tokens(prev_line)
                if overlap_tokens + lt > CHUNK_OVERLAP:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_tokens += lt

            # 使用重叠开始新块
            chunk_lines = overlap_lines + [line]
            chunk_start = i - len(overlap_lines)
            current_tokens = overlap_tokens + line_tokens
        else:
            chunk_lines.append(line)
            current_tokens += line_tokens

    # 输出最后的块
    if chunk_lines:
        content = '\n'.join(chunk_lines)
        yield {
            'content': content,
            'line_start': chunk_start + 1,
            'line_end': chunk_start + len(chunk_lines),
            'file_path': file_path
        }


def content_hash(content: str) -> str:
    """生成内容的哈希用于去重。"""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def index_file(conn: sqlite3.Connection, file_path: Path, force: bool = False):
    """索引单个文件。"""
    if not file_path.exists():
        print(f"文件未找到：{file_path}")
        return

    rel_path = str(file_path.relative_to(PROJECT_DIR))
    text = file_path.read_text()

    if force:
        # 删除此文件的现有块
        cursor = conn.execute(
            "SELECT id FROM chunks WHERE file_path = ?",
            (rel_path,)
        )
        for row in cursor:
            conn.execute("DELETE FROM embeddings WHERE chunk_id = ?", (row['id'],))
        conn.execute("DELETE FROM chunks WHERE file_path = ?", (rel_path,))

    chunks_added = 0
    chunks_skipped = 0

    # 获取当前使用的模型
    config = get_cached_config()
    model = config["model"]

    for chunk in chunk_text(text, rel_path):
        c_hash = content_hash(chunk['content'])

        # 检查块是否已存在
        existing = conn.execute(
            "SELECT id FROM chunks WHERE file_path = ? AND line_start = ? AND content_hash = ?",
            (rel_path, chunk['line_start'], c_hash)
        ).fetchone()

        if existing:
            chunks_skipped += 1
            continue

        # 插入块
        cursor = conn.execute(
            """INSERT INTO chunks (file_path, line_start, line_end, content, content_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (rel_path, chunk['line_start'], chunk['line_end'], chunk['content'], c_hash)
        )
        chunk_id = cursor.lastrowid

        # 获取并存储嵌入
        try:
            embedding = get_embedding(chunk['content'])
            blob = embedding_to_blob(embedding)
            conn.execute(
                "INSERT INTO embeddings (chunk_id, embedding, model) VALUES (?, ?, ?)",
                (chunk_id, blob, model)
            )
            chunks_added += 1
        except Exception as e:
            print(f"  嵌入块时出错：{e}")
            # 如果嵌入失败则删除该块
            conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))

    conn.commit()
    print(f"已索引 {file_path.name}：新增 {chunks_added} 个，跳过 {chunks_skipped} 个")


def index_all(conn: sqlite3.Connection, force: bool = False):
    """索引 memory 目录中的所有 Markdown 文件。"""
    # 如果存在则索引 MEMORY.md
    memory_file = PROJECT_DIR / "MEMORY.md"
    if memory_file.exists():
        index_file(conn, memory_file, force)

    # 索引 memory/ 中的所有文件
    if MEMORY_DIR.exists():
        for md_file in sorted(MEMORY_DIR.glob("*.md")):
            index_file(conn, md_file, force)


def main():
    args = sys.argv[1:]
    force = "--rebuild" in args
    args = [a for a in args if a != "--rebuild"]

    # 显示配置信息
    config = get_cached_config()
    print(f"使用配置：")
    print(f"  Provider: {config.get('provider', 'ollama')}")
    print(f"  Model: {config['model']}")
    print(f"  Base URL: {config['base_url']}")
    print()

    conn = get_db()

    if args:
        # 索引特定文件
        for path in args:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = PROJECT_DIR / path
            index_file(conn, file_path, force)
    else:
        # 索引所有
        index_all(conn, force)

    # 显示统计信息
    count = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()['c']
    print(f"\n数据库中的总块数：{count}")

    conn.close()


if __name__ == "__main__":
    main()
