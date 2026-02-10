#!/usr/bin/env python3
"""
记忆文件监视器 - 当记忆文件更改时自动重新索引。

用法：
    python scripts/watcher.py           # 在前台运行
    python scripts/watcher.py --daemon  # 在后台运行

监视器监控：
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

# 路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
INDEX_SCRIPT = SCRIPT_DIR / "index.py"
MEMORY_DIR = PROJECT_DIR / "memory"
MEMORY_FILE = PROJECT_DIR / "MEMORY.md"

# 防抖设置
DEBOUNCE_SECONDS = 2.0


class MemoryFileHandler(FileSystemEventHandler):
    """当记忆文件更改时重新索引的处理器。"""

    def __init__(self):
        self.pending_files = set()
        self.timer = None
        self.lock = threading.Lock()

    def _should_handle(self, path: str) -> bool:
        """检查此文件是否应触发重新索引。"""
        p = Path(path)
        # 只处理 .md 文件
        if p.suffix != '.md':
            return False
        # 处理 MEMORY.md
        if p == MEMORY_FILE:
            return True
        # 处理 memory/ 中的文件
        if MEMORY_DIR in p.parents or p.parent == MEMORY_DIR:
            return True
        return False

    def _schedule_index(self, file_path: str):
        """使用防抖调度索引。"""
        with self.lock:
            self.pending_files.add(file_path)

            # 取消现有定时器
            if self.timer:
                self.timer.cancel()

            # 调度新定时器
            self.timer = threading.Timer(DEBOUNCE_SECONDS, self._run_index)
            self.timer.start()

    def _run_index(self):
        """对待处理的文件运行索引器。"""
        with self.lock:
            files = list(self.pending_files)
            self.pending_files.clear()
            self.timer = None

        if not files:
            return

        print(f"\n[watcher] 正在索引 {len(files)} 个文件...")
        for f in files:
            print(f"  - {Path(f).name}")

        try:
            # 获取虚拟环境 python
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
            print(f"[watcher] 运行索引器时出错：{e}", file=sys.stderr)

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and self._should_handle(event.src_path):
            self._schedule_index(event.src_path)

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and self._should_handle(event.src_path):
            self._schedule_index(event.src_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="监视记忆文件的更改")
    parser.add_argument("--daemon", "-d", action="store_true", help="在后台运行")
    args = parser.parse_args()

    if args.daemon:
        # Fork 到后台
        import os
        pid = os.fork()
        if pid > 0:
            print(f"[watcher] 在后台启动（PID：{pid}）")
            sys.exit(0)
        # 子进程继续
        os.setsid()

    handler = MemoryFileHandler()
    observer = Observer()

    # 监视项目目录的 MEMORY.md
    observer.schedule(handler, str(PROJECT_DIR), recursive=False)

    # 监视 memory 目录
    if MEMORY_DIR.exists():
        observer.schedule(handler, str(MEMORY_DIR), recursive=True)

    observer.start()
    print(f"[watcher] 正在监视 {PROJECT_DIR} 中的更改")
    print(f"[watcher] 按 Ctrl+C 停止")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[watcher] 正在停止...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
