# Setup Prompts

## Step 1: Installation

Paste this into Claude Code to install the memory system:

```
Set up the claude-code-memory-clawdbot system for me:

1. Clone: git clone https://github.com/JustinPerea/claude-code-memory-clawdbot.git ~/claude-code-memory
2. Run setup: cd ~/claude-code-memory && ./setup.sh
3. Add the memory MCP server to ~/.config/claude-code/.mcp.json (create if needed, merge if exists):
   {
     "mcpServers": {
       "memory": {
         "command": "<HOME>/claude-code-memory/.venv/bin/python",
         "args": ["<HOME>/claude-code-memory/scripts/mcp_server.py"],
         "cwd": "<HOME>/claude-code-memory"
       }
     }
   }
   Replace <HOME> with my actual home directory path.
4. Verify: python ~/claude-code-memory/scripts/session.py status
5. Tell me to restart Claude Code to load the memory tools.
```

## Step 2: Restart Claude Code

Close and reopen Claude Code to load the MCP server.

## Step 3: Teach Claude the Memory System

Paste this into the new session:

```
You now have memory tools available via MCP. Here's how to use them:

1. **memory_search**: Search past context semantically. Use before asking me questions I may have answered before.
   Example: {"query": "database preferences", "maxResults": 6, "minScore": 0.25}

2. **memory_write**: Save important information.
   - Use {"target": "longterm", "content": "..."} for preferences, decisions, important facts
   - Use {"target": "daily", "content": "..."} for session notes

3. **memory_get**: Retrieve specific file content by path and line numbers.

4. **memory_index**: Re-index after manual file edits.

Guidelines:
- Search memory before asking me for context I may have provided before
- Write to longterm memory when I state preferences or make decisions
- Write to daily memory for session summaries and notes

Confirm you understand by searching memory for "test" to verify the tools work.
```

---

## Alternative: Project-Specific Setup

If you want memory instructions built into a specific project, copy `CLAUDE.md` from this repo into your project's root directory. Claude Code will automatically read it.

## Combined Single Prompt (Advanced)

For users who want a single prompt that does everything including teaching Claude:

```
Set up claude-code-memory-clawdbot and teach yourself how to use it:

1. Clone: git clone https://github.com/JustinPerea/claude-code-memory-clawdbot.git ~/claude-code-memory
2. Setup: cd ~/claude-code-memory && ./setup.sh
3. Configure MCP in ~/.config/claude-code/.mcp.json:
   {"mcpServers":{"memory":{"command":"<HOME>/claude-code-memory/.venv/bin/python","args":["<HOME>/claude-code-memory/scripts/mcp_server.py"],"cwd":"<HOME>/claude-code-memory"}}}
   (Replace <HOME> with actual home path, merge with existing config if present)
4. Read ~/claude-code-memory/CLAUDE.md to understand the memory system
5. Tell me to restart Claude Code, then after restart I should paste a follow-up prompt you provide to activate memory usage
```
