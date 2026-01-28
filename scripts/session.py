#!/usr/bin/env python3
"""
Session management helpers for the memory system.

Usage:
    python scripts/session.py flush      # Flush current context to memory
    python scripts/session.py new        # Start a new session (creates new daily log)
    python scripts/session.py summary    # Generate session summary
    python scripts/session.py status     # Show memory system status

These are helper commands that Claude can invoke to manage sessions.
"""

import sys
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "db" / "memory.db"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"


def get_today_log() -> Path:
    """Get path to today's daily log."""
    today = datetime.now().strftime("%Y-%m-%d")
    return MEMORY_DIR / f"{today}.md"


def cmd_status():
    """Show memory system status."""
    print("=== Memory System Status ===\n")

    # Check Ollama
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            print("Ollama: Running")
    except Exception:
        print("Ollama: NOT RUNNING (start with 'brew services start ollama')")

    # Check database
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        file_count = conn.execute("SELECT COUNT(DISTINCT file_path) FROM chunks").fetchone()[0]
        conn.close()
        print(f"Database: {DB_PATH}")
        print(f"  - Chunks indexed: {chunk_count}")
        print(f"  - Files indexed: {file_count}")
    else:
        print("Database: NOT FOUND (run 'python scripts/index.py')")

    # Check memory files
    print(f"\nMemory Files:")
    print(f"  - MEMORY.md: {'exists' if MEMORY_FILE.exists() else 'NOT FOUND'}")

    if MEMORY_DIR.exists():
        logs = sorted(MEMORY_DIR.glob("*.md"), reverse=True)
        print(f"  - Daily logs: {len(logs)} files")
        if logs:
            print(f"  - Latest: {logs[0].name}")
    else:
        print(f"  - Daily logs: directory not found")

    # Today's log
    today_log = get_today_log()
    print(f"\nToday's Log: {today_log.name}")
    if today_log.exists():
        lines = len(today_log.read_text().split('\n'))
        print(f"  - Lines: {lines}")
    else:
        print("  - Not yet created")


def cmd_flush(content: str = None):
    """
    Flush important context to today's log.
    If content is provided, writes it directly.
    Otherwise, prompts for input.
    """
    if content is None:
        print("Enter content to flush to memory (Ctrl+D to finish):")
        try:
            content = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    if not content.strip():
        print("No content to flush.")
        return

    today_log = get_today_log()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H:%M")

    if today_log.exists():
        existing = today_log.read_text()
        new_content = existing.rstrip() + f"\n\n### Memory Flush ({timestamp})\n\n{content.strip()}\n"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = f"# {today}\n\n### Memory Flush ({timestamp})\n\n{content.strip()}\n"

    today_log.write_text(new_content)
    print(f"Flushed to {today_log.name}")

    # Trigger re-index
    _run_index(str(today_log))


def cmd_new(title: str = None):
    """Start a new session section in today's log."""
    today_log = get_today_log()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H:%M")
    session_header = f"## Session ({timestamp})"
    if title:
        session_header = f"## {title} ({timestamp})"

    if today_log.exists():
        existing = today_log.read_text()
        new_content = existing.rstrip() + f"\n\n{session_header}\n\n"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = f"# {today}\n\n{session_header}\n\n"

    today_log.write_text(new_content)
    print(f"New session started in {today_log.name}")


def cmd_summary():
    """Show summary of recent memory activity."""
    print("=== Recent Memory Activity ===\n")

    if not DB_PATH.exists():
        print("No database found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Recent files
    recent = conn.execute("""
        SELECT file_path, COUNT(*) as chunks, MAX(created_at) as last_updated
        FROM chunks
        GROUP BY file_path
        ORDER BY last_updated DESC
        LIMIT 10
    """).fetchall()

    print("Recently Updated Files:")
    for row in recent:
        print(f"  - {row['file_path']} ({row['chunks']} chunks)")

    # Total stats
    stats = conn.execute("""
        SELECT
            COUNT(*) as total_chunks,
            COUNT(DISTINCT file_path) as total_files
        FROM chunks
    """).fetchone()

    print(f"\nTotal: {stats['total_chunks']} chunks across {stats['total_files']} files")

    conn.close()


def cmd_end(summary: str = None, slug: str = None):
    """
    End current session and save context with descriptive filename.

    This mimics Clawdbot's session-memory hook that:
    1. Takes a summary of the session
    2. Generates a descriptive slug for the filename
    3. Saves to memory/YYYY-MM-DD-slug.md
    """
    if summary is None:
        print("Enter session summary (Ctrl+D to finish):")
        try:
            summary = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    if not summary.strip():
        print("No summary provided.")
        return

    # Generate slug from first line or use provided slug
    if slug is None:
        first_line = summary.strip().split('\n')[0]
        # Create slug: lowercase, replace spaces with hyphens, remove special chars
        slug = first_line.lower()
        slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in slug)
        slug = '-'.join(slug.split())[:50]  # Limit length

    if not slug:
        slug = "session"

    # Create filename
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H%M")
    filename = f"{today}-{timestamp}-{slug}.md"
    filepath = MEMORY_DIR / filename

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # Write session file
    content = f"# Session: {slug.replace('-', ' ').title()}\n"
    content += f"**Date**: {today}\n"
    content += f"**Time**: {datetime.now().strftime('%H:%M')}\n\n"
    content += "---\n\n"
    content += summary.strip() + "\n"

    filepath.write_text(content)
    print(f"Session saved to {filename}")

    # Trigger re-index
    _run_index(str(filepath))


def cmd_bootstrap():
    """Show which bootstrap files exist and their status."""
    print("=== Bootstrap Files ===\n")

    bootstrap_files = [
        ("CLAUDE.md", "Agent instructions and memory guidelines"),
        ("SOUL.md", "Personality and communication style"),
        ("USER.md", "User information and preferences"),
        ("TOOLS.md", "Tool usage guidance"),
        ("MEMORY.md", "Long-term curated knowledge"),
    ]

    for filename, description in bootstrap_files:
        filepath = PROJECT_DIR / filename
        if filepath.exists():
            lines = len(filepath.read_text().split('\n'))
            print(f"  ✓ {filename}: {lines} lines")
            print(f"    {description}")
        else:
            print(f"  ✗ {filename}: NOT FOUND")
            print(f"    {description}")
        print()


def _run_index(file_path: str = None):
    """Run the indexer."""
    venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    index_script = SCRIPT_DIR / "index.py"

    cmd = [python_cmd, str(index_script)]
    if file_path:
        cmd.append(file_path)

    subprocess.run(cmd, cwd=PROJECT_DIR)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/session.py <command> [args]")
        print("\nCommands:")
        print("  status    - Show memory system status")
        print("  bootstrap - Check bootstrap files status")
        print("  new       - Start a new session section")
        print("  flush     - Flush content to today's log")
        print("  end       - End session and save with descriptive name")
        print("  summary   - Show recent memory activity")
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
        # Allow --slug flag
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
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
