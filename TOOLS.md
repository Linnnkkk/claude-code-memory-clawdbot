# Tools

This file provides guidance on using external tools effectively.

## Memory Tools (MCP)

### memory_search
Use for finding past context, decisions, or information.
```json
{"query": "database choice", "maxResults": 6, "minScore": 0.25}
```
- Use natural language queries
- Lower minScore (0.1-0.2) for broader results
- Higher minScore (0.4+) for precise matches

### memory_get
Use after search to read full context from a file.
```json
{"path": "memory/2026-01-28.md", "from": 10, "lines": 30}
```

### memory_write
Use to persist important information.
```json
{"target": "longterm", "content": "## Decision\nChose PostgreSQL for..."}
```
- `target: "longterm"` → MEMORY.md (important, persistent)
- `target: "daily"` → memory/YYYY-MM-DD.md (session notes)

### memory_index
Trigger after manually editing memory files.
```json
{"rebuild": false}
```

## CLI Tools (via Bash)

### Session Management
```bash
python scripts/session.py status   # Check system health
python scripts/session.py new      # Start new session section
python scripts/session.py flush    # Save important context
python scripts/session.py summary  # Recent activity
```

### File Watcher
```bash
python scripts/watcher.py          # Auto-index on file changes
python scripts/watcher.py --daemon # Run in background
```

## When to Use What

| Situation | Tool |
|-----------|------|
| "What did we decide about X?" | memory_search |
| User states a preference | memory_write (longterm) |
| End of work session | memory_write (daily) |
| Need full file content | memory_get |
| After manual file edits | memory_index |

## Tool Best Practices

1. **Search before asking** - Check memory before asking user for context they may have provided before
2. **Write incrementally** - Don't wait until session end to write memories
3. **Be specific in queries** - "postgres database decision" > "database"
4. **Index after edits** - Always run memory_index after manually editing .md files

---

*Add guidance for other tools as they're integrated.*
