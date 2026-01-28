# One-Click Setup Prompt

Copy and paste this entire prompt into Claude Code to set up the memory system automatically:

---

```
Set up the claude-code-memory-clawdbot system for me. Do the following steps:

1. Clone the repo if not already present:
   git clone https://github.com/JustinPerea/claude-code-memory-clawdbot.git ~/claude-code-memory

2. Run the setup:
   cd ~/claude-code-memory && ./setup.sh

3. Configure the MCP server by adding to ~/.config/claude-code/.mcp.json:
   - If the file doesn't exist, create it with the memory server config
   - If it exists, add the memory server to the existing mcpServers object
   - Use these values:
     {
       "memory": {
         "command": "$HOME/claude-code-memory/.venv/bin/python",
         "args": ["$HOME/claude-code-memory/scripts/mcp_server.py"],
         "cwd": "$HOME/claude-code-memory"
       }
     }
   - Make sure to expand $HOME to the actual home directory path

4. Verify the setup by running: python ~/claude-code-memory/scripts/session.py status

5. Tell me to restart Claude Code to load the MCP server, then show me how to test it.
```

---

After Claude Code completes the setup, restart Claude Code and test with:
- `memory_search` tool with query "test"
- Or CLI: `python ~/claude-code-memory/scripts/search.py "test"`
