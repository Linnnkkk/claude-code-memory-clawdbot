# 记忆系统

本项目实现了受 Clawdbot 启发的持久化记忆系统。记忆通过 Markdown 文件、向量嵌入和语义搜索跨会话持久化。

## 会话协议

在每个会话开始时，阅读这些引导文件：
1. **SOUL.md** - 个性和沟通风格
2. **USER.md** - 用户信息和偏好
3. **TOOLS.md** - 工具使用指导
4. **MEMORY.md** - 长期精选知识
5. **memory/YYYY-MM-DD.md** - 今天的日志（如果存在）

## 快速参考

| 任务 | 工具/命令 |
|------|--------------|
| 搜索记忆 | `memory_search` MCP 工具 |
| 获取特定内容 | `memory_get` MCP 工具 |
| 写入记忆 | `memory_write` MCP 工具 |
| 重新索引文件 | `memory_index` MCP 工具 |

## 记忆架构

### 引导文件

| 文件 | 用途 |
|------|---------|
| CLAUDE.md | AI 助手指令（本文件） |
| SOUL.md | 个性与语气 |
| USER.md | 用户信息 |
| TOOLS.md | 工具使用指导 |
| MEMORY.md | 长期精选知识 |

### 双层存储

1. **MEMORY.md** - 长期精选知识
   - 用户偏好和决策
   - 重要联系人和参考信息
   - 学到的经验教训

2. **memory/YYYY-MM-DD.md** - 每日日志
   - 会话笔记和观察
   - 对话摘要

### 可用的 MCP 工具

**memory_search** - 语义 + 关键词搜索
```json
{"query": "我们选择了什么数据库", "maxResults": 6, "minScore": 0.25}
```

**memory_get** - 检索特定内容
```json
{"path": "memory/2026-01-28.md", "from": 10, "lines": 20}
```

**memory_write** - 写入记忆
```json
{"target": "daily", "content": "## 决策\n我们选择 PostgreSQL 用于..."}
```

**memory_index** - 触发重新索引
```json
{"path": "memory/2026-01-28.md", "rebuild": false}
```

## 何时使用记忆

### 搜索记忆时：
- 用户询问过去的决策
- 需要之前会话的上下文
- 查找之前讨论过的特定信息

### 写入 MEMORY.md 时：
- 用户说明偏好
- 做出重要决策
- 共享重要信息
- 学到经验教训

### 写入每日日志时：
- 记录会话期间完成的工作
- 记录短期使用的上下文
- 总结对话

## 会话管理（命令行）

```bash
# 检查系统和引导文件
python scripts/session.py status
python scripts/session.py bootstrap

# 会话生命周期
python scripts/session.py new "正在开发 API"     # 开始新的部分
python scripts/session.py flush "重要笔记"       # 快速保存到每日日志
python scripts/session.py end "工作摘要"          # 使用描述性文件名结束会话

# 使用自定义 slug
python scripts/session.py end --slug "api-design" "设计了 REST API..."

# 其他
python scripts/session.py summary                  # 最近活动
```

## 文件结构

```
memory/
├── CLAUDE.md              # AI 助手指令（本文件）
├── SOUL.md                # 个性与语气
├── USER.md                # 用户信息
├── TOOLS.md               # 工具指导
├── MEMORY.md              # 长期精选知识
├── memory/                # 每日日志和会话文件
│   ├── YYYY-MM-DD.md
│   └── YYYY-MM-DD-HHMM-slug.md
├── scripts/
│   ├── mcp_server.py      # MCP 服务器（记忆工具）
│   ├── index.py           # 索引脚本
│   ├── search.py          # 搜索脚本
│   ├── session.py         # 会话管理
│   ├── watcher.py         # 文件监视器
│   └── schema.sql         # 数据库架构
├── db/
│   └── memory.db          # SQLite 带嵌入
└── .venv/                 # Python 环境
```

## 技术细节

- **嵌入**：通过 Ollama 使用 nomic-embed-text（本地、免费）
- **存储**：SQLite 带 FTS5 用于关键词搜索
- **混合搜索**：70% 向量相似度 + 30% BM25 关键词
- **块**：约 400 个 token，80 个 token 重叠
- **最低分数**：0.25（可配置）

## 新项目设置

1. 复制 `scripts/` 文件夹和引导文件
2. 创建虚拟环境：`python -m venv .venv && .venv/bin/pip install watchdog`
3. 创建 `memory/` 目录
4. 确保 Ollama 正在运行：`brew services start ollama`
5. 拉取模型：`ollama pull nomic-embed-text`
6. 将 MCP 服务器添加到 `~/.config/claude-code/.mcp.json`
7. 运行初始索引：`python scripts/index.py`
