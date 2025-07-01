# Claude Code Proxy

A proxy server that enables **Claude Code** to work with OpenAI-compatible API providers. Convert Claude API requests to OpenAI API calls, allowing you to use various LLM providers through the Claude Code CLI.

![Claude Code Proxy](demo.png)

## Features

- **Full Claude API Compatibility**: Complete `/v1/messages` endpoint support
- **Multiple Provider Support**: OpenAI, Azure OpenAI, local models (Ollama), and any OpenAI-compatible API
- **Smart Model Mapping**: Configure BIG and SMALL models via environment variables
- **Function Calling**: Complete tool use support with proper conversion
- **Streaming Responses**: Real-time SSE streaming support
- **Image Support**: Base64 encoded image input
- **Error Handling**: Comprehensive error handling and logging

## Quick Start

### 1. Install Dependencies

```bash
# Using UV (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your API configuration
```

### 3. Start Server

```bash
# Direct run
python start_proxy.py

# Or with UV
uv run claude-code-proxy
```

### 4. Use with Claude Code

```bash
ANTHROPIC_BASE_URL=http://localhost:8082 claude
```

## Configuration

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - Your API key for the target provider

**Model Configuration:**

- `BIG_MODEL` - Model for Claude sonnet/opus requests (default: `gpt-4o`)
- `SMALL_MODEL` - Model for Claude haiku requests (default: `gpt-4o-mini`)

**API Configuration:**

- `OPENAI_BASE_URL` - API base URL (default: `https://api.openai.com/v1`)

**Server Settings:**

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8082`)
- `LOG_LEVEL` - Logging level (default: `WARNING`)

**Performance:**

- `MAX_TOKENS_LIMIT` - Token limit (default: `4096`)
- `MIN_TOKENS_LIMIT` - Minimum token limit (default: `100`)
- `DEFAULT_MAX_TOKENS` - Default max_tokens for requests (default: `1024`)
- `REQUEST_TIMEOUT` - Request timeout in seconds (default: `90`)
- `ENABLE_TOKEN_ESTIMATION` - Enable token estimation when downstream APIs don't provide usage data (default: `true`)

### Token Estimation Feature

When downstream APIs (like some models from Doubao/ByteDance) don't provide accurate token usage information, the proxy can automatically estimate token counts:

- **When Used**: Automatically triggered when downstream API returns zero or missing token usage data
- **Languages Supported**: Handles English, Chinese, and mixed-language text with different estimation ratios
- **Scope**: Estimates both input tokens (from original request) and output tokens (from response content)
- **Logging**: Estimated tokens are clearly marked in logs with "📊 Using estimated tokens..." prefix
- **Configurable**: Can be disabled by setting `ENABLE_TOKEN_ESTIMATION=false`

**Estimation Method:**
- English text: ~4 characters per token
- Chinese text: ~1.2 characters per token  
- Mixed language text: ~2.5 characters per token
- Includes overhead for message formatting and metadata

### Default Max Tokens Feature

The `DEFAULT_MAX_TOKENS` setting provides a fallback value when client requests have invalid or very small `max_tokens` values:

- **When Applied**: Used when client sends `max_tokens` ≤ 0 or below `MIN_TOKENS_LIMIT`
- **Example**: If client sends `max_tokens: 0`, proxy will use `DEFAULT_MAX_TOKENS` value instead
- **Benefit**: Prevents API errors and ensures reasonable response lengths
- **Configurable**: Set via environment variable or .env file

```json
// Client request with invalid max_tokens
{
  "model": "claude-3-haiku",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 0
}

// Converted to downstream API with default value
{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024
}
```

### Token Usage Logging

The proxy automatically logs token usage information to the console when `LOG_LEVEL` is set to `INFO` or `DEBUG`:

- **Non-streaming requests**: Logs after response completion
- **Streaming requests**: Logs when final token counts are available
- **Format**: `🎯 Token Usage | Model: source → target | Input: X | Output: Y | Total: Z`

**Example Console Output:**
```
2025-01-01 10:30:15 - INFO - 🎯 Token Usage | Model: claude-3-haiku → gpt-4o-mini | Input: 15 | Output: 42 | Total: 57
2025-01-01 10:30:20 - INFO - 🎯 Token Usage [Stream] | Model: claude-3-sonnet | Input: 23 | Output: 156 | Total: 179
```

**Configuration:**
```bash
LOG_LEVEL=INFO  # Set to INFO or DEBUG to see token usage logs
```

### Model Mapping

The proxy maps Claude model requests to your configured models:

| Claude Request                 | Mapped To     | Environment Variable   |
| ------------------------------ | ------------- | ---------------------- |
| Models with "haiku"            | `SMALL_MODEL` | Default: `gpt-4o-mini` |
| Models with "sonnet" or "opus" | `BIG_MODEL`   | Default: `gpt-4o`      |

### Provider Examples

#### OpenAI

```bash
OPENAI_API_KEY="sk-your-openai-key"
OPENAI_BASE_URL="https://api.openai.com/v1"
BIG_MODEL="gpt-4o"
SMALL_MODEL="gpt-4o-mini"
```

#### Azure OpenAI

```bash
OPENAI_API_KEY="your-azure-key"
OPENAI_BASE_URL="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
BIG_MODEL="gpt-4"
SMALL_MODEL="gpt-35-turbo"
```

#### Local Models (Ollama)

```bash
OPENAI_API_KEY="dummy-key"  # Required but can be dummy
OPENAI_BASE_URL="http://localhost:11434/v1"
BIG_MODEL="llama3.1:70b"
SMALL_MODEL="llama3.1:8b"
```

#### Other Providers

Any OpenAI-compatible API can be used by setting the appropriate `OPENAI_BASE_URL`.

## Usage Examples

### Basic Chat

```python
import httpx

response = httpx.post(
    "http://localhost:8082/v1/messages",
    json={
        "model": "claude-3-5-sonnet-20241022",  # Maps to BIG_MODEL
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
)
```

## Integration with Claude Code

This proxy is designed to work seamlessly with Claude Code CLI:

```bash
# Start the proxy
python start_proxy.py

# Use Claude Code with the proxy
ANTHROPIC_BASE_URL=http://localhost:8082 claude

# Or set permanently
export ANTHROPIC_BASE_URL=http://localhost:8082
claude
```

## Testing

Test the proxy functionality:

```bash
# Run comprehensive tests
python src/test_claude_to_openai.py
```

## Development

### Using UV

```bash
# Install dependencies
uv sync

# Run server
uv run claude-code-proxy

# Format code
uv run black src/
uv run isort src/

# Type checking
uv run mypy src/
```

### Project Structure

```
claude-code-proxy/
├── src/
│   ├── main.py  # Main server
│   ├── test_claude_to_openai.py    # Tests
│   └── [other modules...]
├── start_proxy.py                  # Startup script
├── .env.example                    # Config template
└── README.md                       # This file
```

## Performance

- **Async/await** for high concurrency
- **Connection pooling** for efficiency
- **Streaming support** for real-time responses
- **Configurable timeouts** and retries
- **Smart error handling** with detailed logging

## License

MIT License
