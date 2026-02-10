#!/usr/bin/env python3
"""
记忆系统的会话管理助手。

用法：
    python scripts/session.py flush      # 将当前上下文刷新到记忆
    python scripts/session.py new        # 开始新会话（创建新的每日日志）
    python scripts/session.py summary    # 生成会话摘要
    python scripts/session.py status     # 显示记忆系统状态

这些是 Claude 可以调用以管理会话的助手命令。
"""

import sys
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"


def get_today_log() -> Path:
    """获取今日每日日志的路径。"""
    today = datetime.now().strftime("%Y-%m-%d")
    return MEMORY_DIR / f"{today}.md"


def cmd_status():
    """显示记忆系统状态。"""
    print("=== 记忆系统状态 ===\n")

    # 检查嵌入 API
    try:
        import urllib.request
        from .config import load_config
        config = load_config()
        provider = config.get("provider", "ollama")

        print(f"嵌入 API：")
        print(f"  - Provider: {provider}")
        print(f"  - Base URL: {config['base_url']}")
        print(f"  - Model: {config['model']}")

        # 测试连接
        if provider == "ollama":
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                print("  - 状态: 正在运行")
        else:
            # OpenAI 或其他 API，简单显示配置
            api_key = config.get("api_key", "")
            print(f"  - API Key: {'已设置' if api_key else '未设置'}")

    except Exception as e:
        print(f"嵌入 API：无法连接 ({e})")

    # 检查数据库
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        file_count = conn.execute("SELECT COUNT(DISTINCT file_path) FROM chunks").fetchone()[0]
        conn.close()
        print(f"\n数据库：{DB_PATH}")
        print(f"  - 已索引块数：{chunk_count}")
        print(f"  - 已索引文件数：{file_count}")
    else:
        print("\n数据库：未找到（运行 'python scripts/index.py'）")

    # 检查记忆文件
    print(f"\n记忆文件：")
    print(f"  - MEMORY.md：{'存在' if MEMORY_FILE.exists() else '未找到'}")

    if MEMORY_DIR.exists():
        logs = sorted(MEMORY_DIR.glob("*.md"), reverse=True)
        print(f"  - 每日日志：{len(logs)} 个文件")
        if logs:
            print(f"  - 最新：{logs[0].name}")
    else:
        print(f"  - 每日日志：目录未找到")

    # 今日日志
    today_log = get_today_log()
    print(f"\n今日日志：{today_log.name}")
    if today_log.exists():
        lines = len(today_log.read_text().split('\n'))
        print(f"  - 行数：{lines}")
    else:
        print("  - 尚未创建")


def cmd_flush(content: str = None):
    """
    将重要上下文刷新到今日日志。
    如果提供了内容，则直接写入。
    否则，提示输入。
    """
    if content is None:
        print("输入要刷新到记忆的内容（Ctrl+D 完成）：")
        try:
            content = sys.stdin.read()
        except KeyboardInterrupt:
            print("\n已取消。")
            return

    if not content.strip():
        print("没有要刷新的内容。")
        return

    today_log = get_today_log()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H:%M")

    if today_log.exists():
        existing = today_log.read_text()
        new_content = existing.rstrip() + f"\n\n### 记忆刷新 ({timestamp})\n\n{content.strip()}\n"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = f"# {today}\n\n### 记忆刷新 ({timestamp})\n\n{content.strip()}\n"

    today_log.write_text(new_content)
    print(f"已刷新到 {today_log.name}")

    # 触发重新索引
    _run_index(str(today_log))


def cmd_new(title: str = None):
    """在今日日志中开始新的会话部分。"""
    today_log = get_today_log()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H:%M")
    session_header = f"## 会话 ({timestamp})"
    if title:
        session_header = f"## {title} ({timestamp})"

    if today_log.exists():
        existing = today_log.read_text()
        new_content = existing.rstrip() + f"\n\n{session_header}\n\n"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = f"# {today}\n\n{session_header}\n\n"

    today_log.write_text(new_content)
    print(f"在 {today_log.name} 中开始了新会话")


def cmd_summary():
    """显示最近记忆活动的摘要。"""
    print("=== 最近记忆活动 ===\n")

    if not DB_PATH.exists():
        print("未找到数据库。")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 最近的文件
    recent = conn.execute("""
        SELECT file_path, COUNT(*) as chunks, MAX(created_at) as last_updated
        FROM chunks
        GROUP BY file_path
        ORDER BY last_updated DESC
        LIMIT 10
    """).fetchall()

    print("最近更新的文件：")
    for row in recent:
        print(f"  - {row['file_path']} ({row['chunks']} 个块)")

    # 总统计
    stats = conn.execute("""
        SELECT
            COUNT(*) as total_chunks,
            COUNT(DISTINCT file_path) as total_files
        FROM chunks
    """).fetchone()

    print(f"\n总计：{stats['total_chunks']} 个块，跨越 {stats['total_files']} 个文件")

    conn.close()


def cmd_end(summary: str = None, slug: str = None):
    """
    结束当前会话并使用描述性文件名保存上下文。

    这模仿了 Clawdbot 的会话记忆钩子，它：
    1. 接收会话摘要
    2. 为文件名生成描述性 slug
    3. 保存到 memory/YYYY-MM-DD-slug.md
    """
    if summary is None:
        print("输入会话摘要（Ctrl+D 完成）：")
        try:
            summary = sys.stdin.read()
        except KeyboardInterrupt:
            print("\n已取消。")
            return

    if not summary.strip():
        print("未提供摘要。")
        return

    # 从第一行生成 slug 或使用提供的 slug
    if slug is None:
        first_line = summary.strip().split('\n')[0]
        # 创建 slug：小写，用连字符替换空格，移除特殊字符
        slug = first_line.lower()
        slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in slug)
        slug = '-'.join(slug.split())[:50]  # 限制长度

    if not slug:
        slug = "session"

    # 创建文件名
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H%M")
    filename = f"{today}-{timestamp}-{slug}.md"
    filepath = MEMORY_DIR / filename

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # 写入会话文件
    content = f"# 会话：{slug.replace('-', ' ').title()}\n"
    content += f"**日期**：{today}\n"
    content += f"**时间**：{datetime.now().strftime('%H:%M')}\n\n"
    content += "---\n\n"
    content += summary.strip() + "\n"

    filepath.write_text(content)
    print(f"会话已保存到 {filename}")

    # 触发重新索引
    _run_index(str(filepath))


def cmd_bootstrap():
    """显示哪些引导文件存在及其状态。"""
    print("=== 引导文件 ===\n")

    bootstrap_files = [
        ("CLAUDE.md", "AI 助手指令和记忆指南"),
        ("SOUL.md", "个性和沟通风格"),
        ("USER.md", "用户信息和偏好"),
        ("TOOLS.md", "工具使用指导"),
        ("MEMORY.md", "长期精选知识"),
    ]

    for filename, description in bootstrap_files:
        filepath = PROJECT_DIR / filename
        if filepath.exists():
            lines = len(filepath.read_text().split('\n'))
            print(f"  ✓ {filename}：{lines} 行")
            print(f"    {description}")
        else:
            print(f"  ✗ {filename}：未找到")
            print(f"    {description}")
        print()


def _run_index(file_path: str = None):
    """运行索引器。"""
    venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    index_script = SCRIPT_DIR / "index.py"

    cmd = [python_cmd, str(index_script)]
    if file_path:
        cmd.append(file_path)

    subprocess.run(cmd, cwd=PROJECT_DIR)


def main():
    if len(sys.argv) < 2:
        print("用法：python scripts/session.py <命令> [参数]")
        print("\n命令：")
        print("  status    - 显示记忆系统状态")
        print("  bootstrap - 检查引导文件状态")
        print("  new       - 开始新的会话部分")
        print("  flush     - 将内容刷新到今日日志")
        print("  end       - 结束会话并使用描述性名称保存")
        print("  summary   - 显示最近记忆活动")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "status":
        cmd_status()
    elif command == "bootstrap":
        cmd_bootstrap()
    elif command == "flush":
        content = ' '.join(args) if args else None
        cmd_flush(content)
    elif command == "new":
        title = ' '.join(args) if args else None
        cmd_new(title)
    elif command == "end":
        # 允许 --slug 标志
        slug = None
        summary_parts = []
        i = 0
        while i < len(args):
            if args[i] == "--slug" and i + 1 < len(args):
                slug = args[i + 1]
                i += 2
            else:
                summary_parts.append(args[i])
                i += 1
        summary = ' '.join(summary_parts) if summary_parts else None
        cmd_end(summary, slug)
    elif command == "summary":
        cmd_summary()
    else:
        print(f"未知命令：{command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
