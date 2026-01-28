# Claude Code Memory

Local, persistent memory system for Claude Code inspired by [Clawdbot's memory architecture](https://manthanguptaa.in/posts/clawdbot_memory/).

## Features

- **Two-layer storage**: Daily logs + curated long-term memory
- **Semantic search**: Vector embeddings via Ollama (local, free)
- **Hybrid search**: 70% vector similarity + 30% BM25 keyword matching
- **MCP integration**: Memory tools available directly in Claude Code
- **Session management**: Track sessions with descriptive filenames
- **Bootstrap files**: Personality, user info, and tool guidance

## Requirements

- macOS or Linux
- Python 3.10+
- [Ollama](https://ollama.ai) (for local embeddings)
- Claude Code

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/claude-code-memory.git
cd claude-code-memory

# Run setup
./setup.sh

# Or manual setup:
python3 -m venv .venv
source .venv/bin/activate
pip install watchdog

# Install Ollama and pull embedding model
brew install ollama
brew services start ollama
ollama pull nomic-embed-text

# Initialize database
python scripts/index.py
```

## Configure MCP Server

Add to `~/.config/claude-code/.mcp.json`:

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

Replace `/path/to/claude-code-memory` with your actual path.

**Restart Claude Code** to load the MCP server.

## MCP Tools

Once configured, these tools are available in Claude Code:

| Tool | Description |
|------|-------------|
| `memory_search` | Semantic + keyword search |
| `memory_get` | Retrieve specific file content |
| `memory_write` | Write to daily or long-term memory |
| `memory_index` | Trigger re-indexing |

### Examples

```json
// Search memories
{"query": "database decision", "maxResults": 6, "minScore": 0.25}

// Get specific content
{"path": "memory/2026-01-28.md", "from": 10, "lines": 20}

// Write to memory
{"target": "longterm", "content": "## Decision\nChose PostgreSQL..."}

// Re-index
{"rebuild": false}
```

## CLI Tools

```bash
# Check system status
python scripts/session.py status

# Check bootstrap files
python scripts/session.py bootstrap

# Start new session section
python scripts/session.py new "Working on feature X"

# Quick save to daily log
python scripts/session.py flush "Important note here"

# End session with descriptive filename
python scripts/session.py end "Summary of what was done"
python scripts/session.py end --slug "api-design" "Designed REST API..."

# Search memories
python scripts/search.py "your query here"

# Manual index
python scripts/index.py

# File watcher (auto-index on changes)
python scripts/watcher.py
```

## File Structure

```
claude-code-memory/
├── CLAUDE.md              # Agent instructions
├── SOUL.md                # Personality/tone (customize)
├── USER.md                # User info (customize)
├── TOOLS.md               # Tool guidance
├── MEMORY.md              # Long-term curated knowledge
├── memory/                # Daily logs
│   └── YYYY-MM-DD.md
├── scripts/
│   ├── mcp_server.py      # MCP server
│   ├── index.py           # Indexing
│   ├── search.py          # Search
│   ├── session.py         # Session management
│   ├── watcher.py         # File watcher
│   └── schema.sql         # Database schema
├── db/
│   └── memory.db          # SQLite database
└── .venv/                 # Python environment
```

## Bootstrap Files

Customize these for your setup:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions and memory guidelines |
| `SOUL.md` | Personality, tone, communication style |
| `USER.md` | Your info, preferences, technical context |
| `TOOLS.md` | Tool usage guidance |
| `MEMORY.md` | Long-term curated knowledge |

## How It Works

1. **Chunking**: Markdown files are split into ~400 token chunks with 80 token overlap
2. **Embedding**: Each chunk is embedded using `nomic-embed-text` via Ollama
3. **Storage**: Chunks and embeddings stored in SQLite with FTS5 for keyword search
4. **Search**: Hybrid scoring (70% cosine similarity + 30% BM25)
5. **Retrieval**: Top results returned with file paths and line numbers

## Configuration

Edit `scripts/search.py` to adjust:

```python
VECTOR_WEIGHT = 0.7      # Weight for semantic similarity
TEXT_WEIGHT = 0.3        # Weight for keyword matching
DEFAULT_LIMIT = 6        # Default number of results
MIN_SCORE = 0.25         # Minimum score threshold
```

## Troubleshooting

**Ollama not running:**
```bash
brew services start ollama
```

**No search results:**
- Lower `minScore` in search query
- Check if files are indexed: `python scripts/session.py status`
- Re-index: `python scripts/index.py --rebuild`

**MCP tools not available:**
- Restart Claude Code after configuring `.mcp.json`
- Check paths in config are absolute and correct

## Credits

Inspired by [Clawdbot's memory architecture](https://manthanguptaa.in/posts/clawdbot_memory/) by Manthan Gupta.

## License

MIT
