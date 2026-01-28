# Memory System

This project implements persistent memory inspired by Clawdbot. Memory persists across sessions via markdown files, vector embeddings, and semantic search.

## Session Protocol

At the start of each session, read these bootstrap files:
1. **SOUL.md** - Personality and communication style
2. **USER.md** - User information and preferences
3. **TOOLS.md** - Tool usage guidance
4. **MEMORY.md** - Long-term curated knowledge
5. **memory/YYYY-MM-DD.md** - Today's log (if exists)

## Quick Reference

| Task | Tool/Command |
|------|--------------|
| Search memories | `memory_search` MCP tool |
| Get specific content | `memory_get` MCP tool |
| Write to memory | `memory_write` MCP tool |
| Re-index files | `memory_index` MCP tool |

## Memory Architecture

### Bootstrap Files

| File | Purpose |
|------|---------|
| CLAUDE.md | Agent instructions (this file) |
| SOUL.md | Personality and tone |
| USER.md | User information |
| TOOLS.md | Tool usage guidance |
| MEMORY.md | Long-term curated knowledge |

### Two-Layer Storage

1. **MEMORY.md** - Long-term curated knowledge
   - User preferences and decisions
   - Important contacts and references
   - Lessons learned

2. **memory/YYYY-MM-DD.md** - Daily logs
   - Session notes and observations
   - Conversation summaries

### MCP Tools Available

**memory_search** - Semantic + keyword search
```json
{"query": "what database did we choose", "maxResults": 6, "minScore": 0.25}
```

**memory_get** - Retrieve specific content
```json
{"path": "memory/2026-01-28.md", "from": 10, "lines": 20}
```

**memory_write** - Write to memory
```json
{"target": "daily", "content": "## Decision\nWe chose PostgreSQL for..."}
```

**memory_index** - Trigger re-indexing
```json
{"path": "memory/2026-01-28.md", "rebuild": false}
```

## When to Use Memory

### Search memories when:
- User asks about past decisions
- Context from previous sessions is needed
- Looking for specific information discussed before

### Write to MEMORY.md when:
- User states a preference
- A significant decision is made
- Important information is shared
- A lesson is learned

### Write to daily log when:
- Noting work done during a session
- Recording context for short-term use
- Summarizing conversations

## Session Management (CLI)

```bash
# Check system and bootstrap files
python scripts/session.py status
python scripts/session.py bootstrap

# Session lifecycle
python scripts/session.py new "Working on API"     # Start new section
python scripts/session.py flush "Important note"   # Quick save to daily log
python scripts/session.py end "Summary of work"    # End session with descriptive file

# With custom slug
python scripts/session.py end --slug "api-design" "Designed the REST API..."

# Other
python scripts/session.py summary                  # Recent activity
```

## File Structure

```
memory/
├── CLAUDE.md              # Agent instructions (this file)
├── SOUL.md                # Personality and tone
├── USER.md                # User information
├── TOOLS.md               # Tool guidance
├── MEMORY.md              # Long-term curated knowledge
├── memory/                # Daily logs and session files
│   ├── YYYY-MM-DD.md
│   └── YYYY-MM-DD-HHMM-slug.md
├── scripts/
│   ├── mcp_server.py      # MCP server (memory tools)
│   ├── index.py           # Indexing script
│   ├── search.py          # Search script
│   ├── session.py         # Session management
│   ├── watcher.py         # File watcher
│   └── schema.sql         # Database schema
├── db/
│   └── memory.db          # SQLite with embeddings
└── .venv/                 # Python environment
```

## Technical Details

- **Embeddings**: nomic-embed-text via Ollama (local, free)
- **Storage**: SQLite with FTS5 for keyword search
- **Hybrid search**: 70% vector similarity + 30% BM25 keyword
- **Chunks**: ~400 tokens with 80 token overlap
- **Min score**: 0.25 (configurable)

## Setup for New Projects

1. Copy `scripts/` folder and bootstrap files
2. Create venv: `python -m venv .venv && .venv/bin/pip install watchdog`
3. Create `memory/` directory
4. Ensure Ollama running: `brew services start ollama`
5. Pull model: `ollama pull nomic-embed-text`
6. Add MCP server to `~/.config/claude-code/.mcp.json`
7. Run initial index: `python scripts/index.py`
