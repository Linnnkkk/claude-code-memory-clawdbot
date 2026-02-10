# Claude 代码记忆系统

受 [Clawdbot 的记忆架构](https://manthanguptaa.in/posts/clawdbot_memory/)启发的 Claude Code 本地持久化记忆系统。

## 一键安装（推荐）

只需将以下提示词粘贴到 Claude Code 中，它将自动完成所有设置：

```
帮我设置 claude-code-memory-clawdbot 系统：

1. 克隆：git clone https://github.com/Linnnkkk/claude-code-memory-clawdbot.git ~/claude-code-memory
2. 运行安装：cd ~/claude-code-memory && ./setup.sh
3. 将记忆 MCP 服务器添加到 ~/.config/claude-code/.mcp.json（如果不存在则创建，如果已存在则合并）：
   {
     "mcpServers": {
       "memory": {
         "command": "<HOME>/claude-code-memory/.venv/bin/python",
         "args": ["<HOME>/claude-code-memory/scripts/mcp_server.py"],
         "cwd": "<HOME>/claude-code-memory"
       }
     }
   }
   将 <HOME> 替换为你的实际主目录路径。
4. 验证：python ~/claude-code-memory/scripts/session.py status
5. 告诉我重启 Claude Code 以加载记忆工具。
```

安装完成后，重启 Claude Code。然后粘贴以下后续提示词以激活记忆系统：

```
你通过 MCP 拥有了持久化记忆工具。你必须主动使用它们——而不仅仅是确认信息。

必需行为：
1. 当我说明偏好、关于我的事实或做出决定时 → 立即调用 memory_write（不要只说"已记录"）
2. 当我询问过去的讨论或上下文时 → 在回答之前先调用 memory_search
3. 在会话结束或重要里程碑时 → 调用 memory_write 记录我们完成的工作

工具：
- memory_write: {"target": "longterm", "content": "## Preferences\n- likes dark themes"} — 用于永久信息
- memory_write: {"target": "daily", "content": "## Session\n- built auth system"} — 用于会话日志
- memory_search: {"query": "user preferences", "maxResults": 6, "minScore": 0.25}
- memory_get: {"path": "memory/2026-01-28.md", "from": 1, "lines": 50}
- memory_index: {"rebuild": false}

重要：实际调用这些工具。如果不说"我会记住这个"而不调用 memory_write，信息将会丢失。

确认工具正常工作：立即使用查询"test"调用 memory_search。
```

对于**特定项目的记忆**，将此仓库中的 `CLAUDE.md` 复制到你的项目目录中。

---

## 功能特性

- **双层存储**：每日日志 + 精选长期记忆
- **语义搜索**：支持多种嵌入 API（Ollama、OpenAI、自定义）
- **混合搜索**：70% 向量相似度 + 30% BM25 关键词匹配
- **灵活配置**：支持自定义 BASE_URL、API Key 和 Model
- **MCP 集成**：记忆工具直接在 Claude Code 中可用
- **会话管理**：使用描述性文件名跟踪会话
- **引导文件**：个性、用户信息和工具指导

## 系统要求

- macOS 或 Linux
- Python 3.10+
- **嵌入 API**（选择其一）：
  - [Ollama](https://ollama.ai)（本地、免费，推荐）
  - OpenAI API（需要 API Key）
  - 其他 OpenAI 兼容的嵌入 API
- Claude Code

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/Linnnkkk/claude-code-memory-clawdbot.git
cd claude-code-memory-clawdbot

# 运行安装脚本（交互式配置）
./setup.sh

# 或手动安装：
python3 -m venv .venv
source .venv/bin/activate
pip install watchdog
```

### 配置嵌入 API

系统支持以下嵌入 API：

#### 选项 1：Ollama（默认，推荐）

```bash
# 安装 Ollama
brew install ollama
brew services start ollama

# 拉取嵌入模型
ollama pull nomic-embed-text
```

配置文件 `.config/embedding.json`：
```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434/api/embeddings",
  "model": "nomic-embed-text",
  "api_key": ""
}
```

#### 选项 2：OpenAI

创建或编辑 `.config/embedding.json`：
```json
{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1/embeddings",
  "model": "text-embedding-3-small",
  "api_key": "sk-your-openai-api-key-here"
}
```

#### 选项 3：自定义 OpenAI 兼容 API

支持任何兼容 OpenAI API 格式的服务（如本地 LLM 服务、第三方 API 等）：

```json
{
  "provider": "openai-compatible",
  "base_url": "https://your-api-endpoint.com/v1/embeddings",
  "model": "your-model-name",
  "api_key": "your-api-key-if-needed"
}
```

**配置说明**：
- 配置文件位置：`.config/embedding.json`（项目根目录）
- 如果配置文件不存在，系统将使用默认的 Ollama 配置
- 示例配置文件：`embedding.example.ollama.json`、`embedding.example.openai.json`
- 修改配置后建议运行 `python scripts/index.py --rebuild` 重新索引

### 初始化数据库

```bash
python scripts/index.py
```

首次运行时会显示当前配置信息，然后开始索引。

## 配置 MCP 服务器

将以下内容添加到 `~/.config/claude-code/.mcp.json`：

```json
{
  "mcpServers": {
    "memory": {
      "command": "/path/to/claude-code-memory/.venv/bin/python",
      "args": ["/path/to/claude-code-memory/scripts/mcp_server.py"],
      "cwd": "/path/to/claude-code-memory"
    }
  }
}
```

将 `/path/to/claude-code-memory` 替换为你的实际路径。

**重启 Claude Code** 以加载 MCP 服务器。

## MCP 工具

配置完成后，以下工具将在 Claude Code 中可用：

| 工具 | 描述 |
|------|-------------|
| `memory_search` | 语义 + 关键词搜索 |
| `memory_get` | 检索特定文件内容 |
| `memory_write` | 写入每日或长期记忆 |
| `memory_index` | 触发重新索引 |

### 使用示例

```json
// 搜索记忆
{"query": "数据库决策", "maxResults": 6, "minScore": 0.25}

// 获取特定内容
{"path": "memory/2026-01-28.md", "from": 10, "lines": 20}

// 写入记忆
{"target": "longterm", "content": "## 决策\n选择了 PostgreSQL..."}

// 重新索引
{"rebuild": false}
```

## 命令行工具

```bash
# 检查系统状态
python scripts/session.py status

# 检查引导文件
python scripts/session.py bootstrap

# 开始新的会话部分
python scripts/session.py new "正在开发功能 X"

# 快速保存到每日日志
python scripts/session.py flush "重要笔记"

# 使用描述性文件名结束会话
python scripts/session.py end "完成工作摘要"
python scripts/session.py end --slug "api-design" "设计了 REST API..."

# 搜索记忆
python scripts/search.py "你的查询内容"

# 手动索引
python scripts/index.py

# 重建索引（更改配置后使用）
python scripts/index.py --rebuild

# 文件监视器（文件更改时自动索引）
python scripts/watcher.py
```

## 文件结构

```
claude-code-memory/
├── CLAUDE.md                      # AI 助手指令
├── SOUL.md                        # 个性/语气（可自定义）
├── USER.md                        # 用户信息（可自定义）
├── TOOLS.md                       # 工具使用指导
├── MEMORY.md                      # 长期精选知识
├── memory/                        # 每日日志
│   └── YYYY-MM-DD.md
├── scripts/
│   ├── config.py                  # 配置加载模块
│   ├── embedding_client.py        # 通用嵌入客户端
│   ├── mcp_server.py              # MCP 服务器
│   ├── index.py                   # 索引
│   ├── search.py                  # 搜索
│   ├── session.py                 # 会话管理
│   ├── watcher.py                 # 文件监视器
│   └── schema.sql                 # 数据库架构
├── .config/
│   └── embedding.json             # 嵌入 API 配置
├── embedding.example.ollama.json  # Ollama 配置示例
├── embedding.example.openai.json  # OpenAI 配置示例
├── db/
│   └── memory.db                  # SQLite 数据库
└── .venv/                         # Python 环境
```

## 引导文件

根据你的设置自定义这些文件：

| 文件 | 用途 |
|------|---------|
| `CLAUDE.md` | AI 助手指令和记忆指南 |
| `SOUL.md` | 个性、语气、沟通风格 |
| `USER.md` | 你的信息、偏好、技术背景 |
| `TOOLS.md` | 工具使用指导 |
| `MEMORY.md` | 长期精选知识 |

## 工作原理

1. **分块**：Markdown 文件被分割成约 400 个 token 的块，具有 80 个 token 的重叠
2. **嵌入**：每个块通过配置的嵌入 API 进行向量化
3. **存储**：块和嵌入存储在 SQLite 中，使用 FTS5 进行关键词搜索
4. **搜索**：混合评分（70% 余弦相似度 + 30% BM25）
5. **检索**：返回带有文件路径和行号的最佳结果

## 配置调整

### 搜索参数

编辑 `scripts/search.py` 以调整：

```python
VECTOR_WEIGHT = 0.7      # 语义相似度权重
TEXT_WEIGHT = 0.3        # 关键词匹配权重
DEFAULT_LIMIT = 6        # 默认结果数量
MIN_SCORE = 0.25         # 最低分数阈值
```

### 嵌入 API 配置

编辑 `.config/embedding.json` 或运行 `python scripts/embedding_client.py` 测试配置：

```bash
python scripts/embedding_client.py "测试文本"
```

## 故障排除

**嵌入 API 连接失败：**
- 检查 `.config/embedding.json` 配置是否正确
- 运行 `python scripts/embedding_client.py "测试"` 测试连接
- 确认 API 服务正在运行（Ollama: `ollama list`）

**没有搜索结果：**
- 降低搜索查询中的 `minScore`
- 检查文件是否已索引：`python scripts/session.py status`
- 重新索引：`python scripts/index.py --rebuild`

**MCP 工具不可用：**
- 配置 `.mcp.json` 后重启 Claude Code
- 检查配置中的路径是否为绝对路径且正确
- 查看是否有错误日志

**配置更改后索引失败：**
- 如果更换了嵌入模型，需要重建整个索引：`python scripts/index.py --rebuild`
- 不同模型的嵌入维度不同，无法混合使用

## 从旧版本升级

如果你之前使用的是硬编码 Ollama 版本：

1. 更新代码后，如果继续使用 Ollama，无需额外配置
2. 系统会自动使用默认的 Ollama 配置
3. 如需切换到其他 API，创建 `.config/embedding.json` 并运行 `python scripts/index.py --rebuild`

## 致谢

受 Manthan Gupta 的 [Clawdbot 记忆架构](https://manthanguptaa.in/posts/clawdbot_memory/) 启发。

## 许可证

MIT
