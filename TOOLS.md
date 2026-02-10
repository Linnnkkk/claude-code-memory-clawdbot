# 工具

此文件提供了有效使用外部工具的指导。

## 记忆工具（MCP）

### memory_search
用于查找过去的上下文、决策或信息。
```json
{"query": "数据库选择", "maxResults": 6, "minScore": 0.25}
```
- 使用自然语言查询
- 较低的 minScore（0.1-0.2）获得更广泛的结果
- 较高的 minScore（0.4+）获得精确匹配

### memory_get
在搜索后用于从文件中读取完整上下文。
```json
{"path": "memory/2026-01-28.md", "from": 10, "lines": 30}
```

### memory_write
用于持久化重要信息。
```json
{"target": "longterm", "content": "## 决策\n选择了 PostgreSQL 用于..."}
```
- `target: "longterm"` → MEMORY.md（重要、持久）
- `target: "daily"` → memory/YYYY-MM-DD.md（会话笔记）

### memory_index
在手动编辑记忆文件后触发。
```json
{"rebuild": false}
```

## 命令行工具（通过 Bash）

### 会话管理
```bash
python scripts/session.py status   # 检查系统健康状况
python scripts/session.py new      # 开始新的会话部分
python scripts/session.py flush    # 保存重要上下文
python scripts/session.py summary  # 最近活动
```

### 文件监视器
```bash
python scripts/watcher.py          # 文件更改时自动索引
python scripts/watcher.py --daemon # 在后台运行
```

## 何时使用什么

| 情况 | 工具 |
|-----------|------|
| "我们关于 X 做出了什么决定？" | memory_search |
| 用户说明偏好 | memory_write (longterm) |
| 工作会话结束 | memory_write (daily) |
| 需要完整文件内容 | memory_get |
| 手动文件编辑后 | memory_index |

## 工具最佳实践

1. **搜索后再询问** - 在向用户询问他们可能之前提供的上下文之前，先检查记忆
2. **增量写入** - 不要等到会话结束才写入记忆
3. **查询要具体** - "postgres 数据库决策" > "数据库"
4. **编辑后索引** - 在手动编辑 .md 文件后始终运行 memory_index

---

*添加其他工具的指导，当它们被集成时。*
