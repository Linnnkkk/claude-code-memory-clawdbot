#!/usr/bin/env python3
"""
Memory file watcher - automatically re-indexes memory files when they change.

Usage:
    python scripts/watcher.py           # Run in foreground
    python scripts/watcher.py --daemon  # Run in background

The watcher monitors:
    - MEMORY.md
    - memory/*.md
"""

import sys
import time
import subprocess
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
INDEX_SCRIPT = SCRIPT_DIR / "index.py"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"

# Debounce settings
DEBOUNCE_SECONDS = 2.0


class MemoryFileHandler(FileSystemEventHandler):
    """Handler that re-indexes when memory files change."""

    def __init__(self):
        self.pending_files = set()
        self.timer = None
        self.lock = threading.Lock()

    def _should_handle(self, path: str) -> bool:
        """Check if this file should trigger re-indexing."""
        p = Path(path)
        # Only handle .md files
        if p.suffix != '.md':
            return False
        # Handle MEMORY.md
        if p == MEMORY_FILE:
            return True
        # Handle files in memory/
        if MEMORY_DIR in p.parents or p.parent == MEMORY_DIR:
            return True
        return False

    def _schedule_index(self, file_path: str):
        """Schedule indexing with debounce."""
        with self.lock:
            self.pending_files.add(file_path)

            # Cancel existing timer
            if self.timer:
                self.timer.cancel()

            # Schedule new timer
            self.timer = threading.Timer(DEBOUNCE_SECONDS, self._run_index)
            self.timer.start()

    def _run_index(self):
        """Run the indexer on pending files."""
        with self.lock:
            files = list(self.pending_files)
            self.pending_files.clear()
            self.timer = None

        if not files:
            return

        print(f"\n[watcher] Indexing {len(files)} file(s)...")
        for f in files:
            print(f"  - {Path(f).name}")

        try:
            # Get the venv python
            venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
            python_cmd = str(venv_python) if venv_python.exists() else sys.executable

            result = subprocess.run(
                [python_cmd, str(INDEX_SCRIPT)] + files,
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        except Exception as e:
            print(f"[watcher] Error running indexer: {e}", file=sys.stderr)

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and self._should_handle(event.src_path):
            self._schedule_index(event.src_path)

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and self._should_handle(event.src_path):
            self._schedule_index(event.src_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Watch memory files for changes")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run in background")
    args = parser.parse_args()

    if args.daemon:
        # Fork to background
        import os
        pid = os.fork()
        if pid > 0:
            print(f"[watcher] Started in background (PID: {pid})")
            sys.exit(0)
        # Child process continues
        os.setsid()

    handler = MemoryFileHandler()
    observer = Observer()

    # Watch project directory for MEMORY.md
    observer.schedule(handler, str(PROJECT_DIR), recursive=False)

    # Watch memory directory
    if MEMORY_DIR.exists():
        observer.schedule(handler, str(MEMORY_DIR), recursive=True)

    observer.start()
    print(f"[watcher] Watching for changes in {PROJECT_DIR}")
    print(f"[watcher] Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[watcher] Stopping...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
