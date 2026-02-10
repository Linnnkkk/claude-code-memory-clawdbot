# 配置文档

## 嵌入 API 配置

记忆系统支持多种嵌入 API 提供商。通过配置文件 `.config/embedding.json` 来指定使用的 API。

### 配置文件位置

- 路径：`.config/embedding.json`（项目根目录）
- 格式：JSON

### 配置文件结构

```json
{
  "provider": "ollama | openai | openai-compatible",
  "base_url": "API 端点 URL",
  "model": "模型名称",
  "api_key": "API Key（可选，Ollama 可以为空）"
}
```

### 字段说明

| 字段 | 必需 | 说明 |
|------|------|------|
| `provider` | 是 | API 类型：`ollama`、`openai` 或 `openai-compatible` |
| `base_url` | 是 | API 端点的完整 URL |
| `model` | 是 | 使用的嵌入模型名称 |
| `api_key` | 否 | API 密钥（Ollama 不需要，OpenAI 需要） |

## 配置示例

### Ollama（本地）

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434/api/embeddings",
  "model": "nomic-embed-text",
  "api_key": ""
}
```

**说明**：
- 使用本地运行的 Ollama 服务
- 需要先拉取模型：`ollama pull nomic-embed-text`
- 不需要 API Key

### OpenAI

```json
{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1/embeddings",
  "model": "text-embedding-3-small",
  "api_key": "sk-your-openai-api-key-here"
}
```

**说明**：
- 使用 OpenAI 官方 API
- 需要有效的 API Key
- 支持的模型：`text-embedding-3-small`、`text-embedding-3-large`、`text-embedding-ada-002`

### 自定义 OpenAI 兼容 API

```json
{
  "provider": "openai-compatible",
  "base_url": "https://your-api-endpoint.com/v1/embeddings",
  "model": "your-model-name",
  "api_key": "your-api-key-if-needed"
}
```

**说明**：
- 支持任何兼容 OpenAI API 格式的服务
- 可以是本地 LLM 服务（如 Ollama 的 OpenAI 兼容模式）
- 可以是第三方 API 服务
- 如果不需要 API Key，可以留空或删除此字段

## 默认配置

如果配置文件不存在，系统将使用以下默认配置：

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434/api/embeddings",
  "model": "nomic-embed-text",
  "api_key": ""
}
```

这确保了与旧版本的向后兼容性。

## 切换 API 提供商

1. 创建或编辑 `.config/embedding.json`
2. 设置新的配置值
3. 重建索引（**重要**）：
   ```bash
   python scripts/index.py --rebuild
   ```

**注意**：不同模型的嵌入向量维度不同，必须重建索引才能正常工作。

## 测试配置

运行以下命令测试配置是否正确：

```bash
python scripts/embedding_client.py "测试文本"
```

预期输出：
```
配置：
  Provider: ollama
  Base URL: http://localhost:11434/api/embeddings
  Model: nomic-embed-text
  API Key: 未设置

测试嵌入：测试文本
嵌入维度：768
前 10 个值：[0.1234, 0.5678, ...]
```

## API 格式说明

### Ollama API

**请求**：
```http
POST /api/embeddings
Content-Type: application/json

{
  "model": "nomic-embed-text",
  "prompt": "要嵌入的文本"
}
```

**响应**：
```json
{
  "embedding": [0.1, 0.2, ...]
}
```

### OpenAI 兼容 API

**请求**：
```http
POST /v1/embeddings
Content-Type: application/json
Authorization: Bearer sk-xxxxx

{
  "model": "text-embedding-3-small",
  "input": "要嵌入的文本"
}
```

**响应**：
```json
{
  "data": [
    {
      "embedding": [0.1, 0.2, ...]
    }
  ]
}
```

## 推荐配置

### 开发环境（免费）
- **提供商**：Ollama
- **模型**：nomic-embed-text
- **优点**：完全免费、本地运行、无需 API Key
- **缺点**：需要本地运行 Ollama 服务

### 生产环境（高精度）
- **提供商**：OpenAI
- **模型**：text-embedding-3-small
- **优点**：精度高、稳定性好
- **缺点**：需要付费、需要 API Key

### 自托管
- **提供商**：openai-compatible
- **模型**：根据你的服务选择
- **优点**：数据隐私、可控性强
- **缺点**：需要自己维护服务

## 常见问题

### Q: 更改配置后搜索没有结果？
A: 需要重建索引：`python scripts/index.py --rebuild`

### Q: 可以同时使用多个模型吗？
A: 不可以。每次只能使用一个模型，所有嵌入必须来自同一模型才能计算相似度。

### Q: 如何验证 API 连接？
A: 运行 `python scripts/embedding_client.py "测试"` 检查连接和嵌入输出。

### Q: 配置文件路径错误怎么办？
A: 确保配置文件位于项目根目录的 `.config/embedding.json`。使用绝对路径检查。

### Q: 如何在 Docker 中使用？
A: 将 `.config/embedding.json` 作为 volume 挂载到容器中。

## 配置文件参考

项目根目录提供了两个示例配置文件：
- `embedding.example.ollama.json` - Ollama 配置示例
- `embedding.example.openai.json` - OpenAI 配置示例
