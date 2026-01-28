#!/bin/bash
set -e

echo "=== Claude Code Memory Setup ==="
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION"
else
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

# Create virtual environment
echo
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${YELLOW}→${NC} Virtual environment already exists"
fi

# Activate and install dependencies
echo
echo "Installing Python dependencies..."
source .venv/bin/activate
pip install -q watchdog
echo -e "${GREEN}✓${NC} Dependencies installed"

# Check Ollama
echo
echo "Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓${NC} Ollama installed"
else
    echo -e "${YELLOW}→${NC} Ollama not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ollama
        echo -e "${GREEN}✓${NC} Ollama installed"
    else
        echo -e "${RED}✗ Homebrew not found. Please install Ollama manually: https://ollama.ai${NC}"
        exit 1
    fi
fi

# Start Ollama
echo
echo "Starting Ollama service..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Ollama already running"
else
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start ollama 2>/dev/null || ollama serve &
    else
        ollama serve &
    fi
    sleep 2
    echo -e "${GREEN}✓${NC} Ollama started"
fi

# Pull embedding model
echo
echo "Pulling embedding model (nomic-embed-text)..."
if ollama list | grep -q "nomic-embed-text"; then
    echo -e "${GREEN}✓${NC} Model already downloaded"
else
    ollama pull nomic-embed-text
    echo -e "${GREEN}✓${NC} Model downloaded"
fi

# Create directories
echo
echo "Creating directories..."
mkdir -p memory db
echo -e "${GREEN}✓${NC} Directories created"

# Initialize database
echo
echo "Initializing database..."
.venv/bin/python scripts/index.py
echo -e "${GREEN}✓${NC} Database initialized"

# Generate MCP config snippet
echo
echo "=== MCP Configuration ==="
echo
echo "Add this to ~/.config/claude-code/.mcp.json:"
echo
cat << EOF
{
  "mcpServers": {
    "memory": {
      "command": "$SCRIPT_DIR/.venv/bin/python",
      "args": ["$SCRIPT_DIR/scripts/mcp_server.py"],
      "cwd": "$SCRIPT_DIR"
    }
  }
}
EOF

echo
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo
echo "Next steps:"
echo "1. Add the MCP config above to ~/.config/claude-code/.mcp.json"
echo "2. Customize USER.md, SOUL.md, and MEMORY.md"
echo "3. Restart Claude Code"
echo "4. Test with: python scripts/session.py status"
