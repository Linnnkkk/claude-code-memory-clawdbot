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

## Step 3: Activate Memory System

Paste this into the new session:

```
You have persistent memory tools via MCP. You MUST actively use them - not just acknowledge information.

REQUIRED BEHAVIORS:
1. When I state a preference, fact about me, or make a decision → IMMEDIATELY call memory_write (don't just say "noted")
2. When I ask about past discussions or context → FIRST call memory_search before answering
3. At session end or major milestones → call memory_write to log what we accomplished

TOOLS:
- memory_write: {"target": "longterm", "content": "## Preferences\n- likes dark themes"} — for permanent info
- memory_write: {"target": "daily", "content": "## Session\n- built auth system"} — for session logs
- memory_search: {"query": "user preferences", "maxResults": 6, "minScore": 0.25}
- memory_get: {"path": "memory/2026-01-28.md", "from": 1, "lines": 50}
- memory_index: {"rebuild": false}

IMPORTANT: Actually CALL the tools. Saying "I'll remember that" without calling memory_write means it will be lost.

Confirm tools work: call memory_search with query "test" RIGHT NOW.
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
