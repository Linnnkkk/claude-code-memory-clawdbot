# 设置提示词

## 第一步：安装

将此粘贴到 Claude Code 中以安装记忆系统：

```
为我设置 claude-code-memory-clawdbot 系统：

1. 克隆：git clone https://github.com/Linnnkkk/claude-code-memory-clawdbot.git ~/claude-code-memory
2. 运行设置：cd ~/claude-code-memory && ./setup.sh
3. 将记忆 MCP 服务器添加到 ~/.config/claude-code/.mcp.json（如果不存在则创建，如果存在则合并）：
   {
     "mcpServers": {
       "memory": {
         "command": "<HOME>/claude-code-memory/.venv/bin/python",
         "args": ["<HOME>/claude-code-memory/scripts/mcp_server.py"],
         "cwd": "<HOME>/claude-code-memory"
       }
     }
   }
   将 <HOME> 替换为我实际的用户主目录路径。
4. 验证：python ~/claude-code-memory/scripts/session.py status
5. 告诉我重启 Claude Code 以加载记忆工具。
```

## 第二步：重启 Claude Code

关闭并重新打开 Claude Code 以加载 MCP 服务器。

## 第三步：激活记忆系统

将此粘贴到新会话中：

```
你已通过 MCP 拥有持久性记忆工具。你必须积极使用它们——不能只是确认信息。

必需行为：
1. 当我陈述偏好、关于我的事实或做出决定时 → 立即调用 memory_write（不要只说“已记下”）
2. 当我询问过去的讨论或上下文时 → 在回答之前首先调用 memory_search
3. 在会话结束或主要里程碑时 → 调用 memory_write 记录我们完成的工作

工具：
- memory_write: {"target": "longterm", "content": "## 偏好\n- 喜欢深色主题"} — 用于永久性信息
- memory_write: {"target": "daily", "content": "## 会话\n- 构建了认证系统"} — 用于会话日志
- memory_search: {"query": "用户偏好", "maxResults": 6, "minScore": 0.25}
- memory_get: {"path": "memory/2026-01-28.md", "from": 1, "lines": 50}
- memory_index: {"rebuild": false}

重要提示：务必实际调用这些工具。只说“我会记住”而不调用 memory_write 意味着信息将会丢失。

确认工具工作：立即调用 memory_search，查询 "test"。
```

---

## 替代方案：项目特定设置

如果你想将记忆指令内置到特定项目中，请将此仓库中的 `CLAUDE.md` 文件复制到你项目的根目录。Claude Code 会自动读取它。

## 组合单条提示词（高级）

适用于希望一条提示词完成所有操作（包括教给 Claude）的用户：

```
设置 claude-code-memory-clawdbot 并教会你自己如何使用它：

1. 克隆：git clone https://github.com/Linnnkkk/claude-code-memory-clawdbot.git ~/claude-code-memory
2. 设置：cd ~/claude-code-memory && ./setup.sh
3. 在 ~/.config/claude-code/.mcp.json 中配置 MCP：
   {"mcpServers":{"memory":{"command":"<HOME>/claude-code-memory/.venv/bin/python","args":["<HOME>/claude-code-memory/scripts/mcp_server.py"],"cwd":"<HOME>/claude-code-memory"}}}
   （将 <HOME> 替换为实际的主目录路径，如果已有配置则合并）
4. 阅读 ~/claude-code-memory/CLAUDE.md 以了解记忆系统
5. 告诉我重启 Claude Code，重启后我应该粘贴你提供的后续提示词来激活记忆使用
```
