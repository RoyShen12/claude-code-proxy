# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- **Install dependencies**: `uv sync` (recommended) or `pip install -r requirements.txt`
- **Start server**: `python start_proxy.py` or `uv run claude-code-proxy`
- **Format code**: 
  - `uv run black src/`
  - `uv run isort src/`
- **Type checking**: `uv run mypy src/`
- **Run tests**: `python src/test_claude_to_openai.py`

## Code Architecture

The project is a proxy server that converts Claude API requests to OpenAI API calls. Key components:

1. **API Endpoints** (`src/api/endpoints.py`):
   - FastAPI implementation handling `/v1/messages` endpoint
   - Converts Claude requests to OpenAI format

2. **Request/Response Conversion** (`src/conversion/`):
   - `request_converter.py`: Maps Claude models/parameters to OpenAI equivalents
   - `response_converter.py`: Transforms OpenAI responses to Claude format

3. **Model Management** (`src/core/model_manager.py`):
   - Handles model mapping configuration (BIG_MODEL/SMALL_MODEL)
   - Dynamically selects models based on Claude request parameters

4. **Client Layer** (`src/core/client.py`):
   - Async HTTP client for forwarding requests to OpenAI API
   - Implements timeout, retry, and error handling logic

5. **Configuration** (`src/core/config.py`):
   - Centralized environment variable management
   - Validation for required settings like API keys

Key architectural features:
- Async/await implementation for high concurrency
- Full streaming response support (SSE)
- Comprehensive error mapping between OpenAI and Claude error formats
- Configurable model mapping via environment variables
- Support for multiple providers (OpenAI, Azure, Ollama)

## Development Guidelines

- Use `uv` for task execution instead of raw commands
- Always maintain compatibility with Claude API specifications
- Tests should cover all critical conversion paths (`src/test_claude_to_openai.py`)
- Add new providers by extending the client and model mapping systems
- Use Pydantic models for all request/response objects