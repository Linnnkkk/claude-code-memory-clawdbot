#!/bin/bash
set -e

echo "=== Claude 代码记忆系统安装 ==="
echo

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python
echo "检查 Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION"
else
    echo -e "${RED}✗ 未找到 Python 3。请安装 Python 3.10+${NC}"
    exit 1
fi

# 创建虚拟环境
echo
echo "创建虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✓${NC} 虚拟环境已创建"
else
    echo -e "${YELLOW}→${NC} 虚拟环境已存在"
fi

# 激活并安装依赖
echo
echo "安装 Python 依赖..."
source .venv/bin/activate
pip install -q watchdog
echo -e "${GREEN}✓${NC} 依赖已安装"

# 检查嵌入 API 配置
echo
echo "配置嵌入 API..."

CONFIG_FILE=".config/embedding.json"

if [ -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}→${NC} 配置文件已存在：$CONFIG_FILE"
else
    echo -e "${YELLOW}→${NC} 未找到配置文件"
    echo
    echo "请选择嵌入 API 提供商："
    echo "  1) Ollama（本地，推荐）"
    echo "  2) OpenAI（需要 API Key）"
    echo "  3) 自定义 OpenAI 兼容 API"
    echo
    read -p "选择 [1-3] (默认 1): " choice
    choice=${choice:-1}

    mkdir -p .config

    case $choice in
        1)
            # Ollama
            cat > "$CONFIG_FILE" << 'EOF'
{
  "provider": "ollama",
  "base_url": "http://localhost:11434/api/embeddings",
  "model": "nomic-embed-text",
  "api_key": ""
}
EOF
            echo -e "${GREEN}✓${NC} 已配置 Ollama"

            # 检查并安装 Ollama
            echo
            echo "检查 Ollama..."
            if command -v ollama &> /dev/null; then
                echo -e "${GREEN}✓${NC} Ollama 已安装"
            else
                echo -e "${YELLOW}→${NC} 未找到 Ollama。正在通过 Homebrew 安装..."
                if command -v brew &> /dev/null; then
                    brew install ollama
                    echo -e "${GREEN}✓${NC} Ollama 已安装"
                else
                    echo -e "${RED}✗ 未找到 Homebrew。请手动安装 Ollama：https://ollama.ai${NC}"
                fi
            fi

            # 启动 Ollama
            echo
            echo "启动 Ollama 服务..."
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC} Ollama 已在运行"
            else
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    brew services start ollama 2>/dev/null || ollama serve &
                else
                    ollama serve &
                fi
                sleep 2
                echo -e "${GREEN}✓${NC} Ollama 已启动"
            fi

            # 拉取嵌入模型
            echo
            echo "正在拉取嵌入模型（nomic-embed-text）..."
            if ollama list | grep -q "nomic-embed-text"; then
                echo -e "${GREEN}✓${NC} 模型已下载"
            else
                ollama pull nomic-embed-text
                echo -e "${GREEN}✓${NC} 模型已下载"
            fi
            ;;

        2)
            # OpenAI
            read -p "请输入 OpenAI API Key: " api_key
            if [ -z "$api_key" ]; then
                echo -e "${RED}✗ API Key 不能为空${NC}"
                exit 1
            fi
            cat > "$CONFIG_FILE" << EOF
{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1/embeddings",
  "model": "text-embedding-3-small",
  "api_key": "$api_key"
}
EOF
            echo -e "${GREEN}✓${NC} 已配置 OpenAI"
            ;;

        3)
            # 自定义
            read -p "请输入 API Base URL: " base_url
            read -p "请输入 Model 名称: " model
            read -p "请输入 API Key (可选，按回车跳过): " api_key

            if [ -z "$base_url" ] || [ -z "$model" ]; then
                echo -e "${RED}✗ Base URL 和 Model 不能为空${NC}"
                exit 1
            fi

            if [ -z "$api_key" ]; then
                api_key='""'
            else
                api_key="\"$api_key\""
            fi

            cat > "$CONFIG_FILE" << EOF
{
  "provider": "openai-compatible",
  "base_url": "$base_url",
  "model": "$model",
  "api_key": $api_key
}
EOF
            echo -e "${GREEN}✓${NC} 已配置自定义 API"
            ;;
    esac
fi

# 显示当前配置
echo
echo "当前配置："
python3 -c "
import json
import sys
sys.path.insert(0, '.')
from scripts.config import load_config
config = load_config()
print(f\"  Provider: {config.get('provider', 'ollama')}\")
print(f\"  Base URL: {config['base_url']}\")
print(f\"  Model: {config['model']}\")
api_key = config.get('api_key', '')
print(f\"  API Key: {'已设置' if api_key else '未设置'}\")
"

# 创建目录
echo
echo "创建目录..."
mkdir -p memory db
echo -e "${GREEN}✓${NC} 目录已创建"

# 初始化数据库
echo
echo "初始化数据库..."
.venv/bin/python scripts/index.py
echo -e "${GREEN}✓${NC} 数据库已初始化"

# 生成 MCP 配置片段
echo
echo "=== MCP 配置 ==="
echo
echo "将以下内容添加到 ~/.config/claude-code/.mcp.json："
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
echo -e "${GREEN}=== 安装完成 ===${NC}"
echo
echo "后续步骤："
echo "1. 将上述 MCP 配置添加到 ~/.config/claude-code/.mcp.json"
echo "2. 自定义 USER.md、SOUL.md 和 MEMORY.md"
echo "3. 重启 Claude Code"
echo "4. 使用以下命令测试：python scripts/session.py status"
echo
echo "配置说明："
echo "- 配置文件位置：.config/embedding.json"
echo "- 示例配置：embedding.example.ollama.json, embedding.example.openai.json"
echo "- 修改配置后需要重建索引：python scripts/index.py --rebuild"
