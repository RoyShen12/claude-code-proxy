from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from src.api.endpoints import router as api_router
import uvicorn
import sys
import logging
from src.core.config import config

# Setup basic logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Claude-to-OpenAI API Proxy", version="1.0.0")

# Global exception handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPExceptions with proper error response format."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "status_code": exc.status_code,
                "message": exc.detail
            }
        }
    )

# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other unhandled exceptions."""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    import traceback
    logger.error(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "status_code": 500,
                "message": "Internal server error occurred"
            }
        }
    )

app.include_router(api_router)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Claude-to-OpenAI API Proxy v1.0.0")
        print("")
        print("Usage: python src/main.py")
        print("")
        print("Required environment variables:")
        print("  OPENAI_API_KEY - Your OpenAI API key")
        print("")
        print("Optional environment variables:")
        print(
            f"  OPENAI_BASE_URL - OpenAI API base URL (default: https://api.openai.com/v1)"
        )
        print(f"  BIG_MODEL - Model for sonnet/opus requests (default: gpt-4o)")
        print(f"  SMALL_MODEL - Model for haiku requests (default: gpt-4o-mini)")
        print(f"  HOST - Server host (default: 0.0.0.0)")
        print(f"  PORT - Server port (default: 8082)")
        print(f"  LOG_LEVEL - Logging level (default: WARNING)")
        print(f"  MAX_TOKENS_LIMIT - Token limit (default: 4096)")
        print(f"  MIN_TOKENS_LIMIT - Minimum token limit (default: 100)")
        print(f"  DEFAULT_MAX_TOKENS - Default max_tokens for requests (default: 1024)")
        print(f"  REQUEST_TIMEOUT - Request timeout in seconds (default: 90)")
        print("")
        print("Model mapping:")
        print(f"  Claude haiku models -> {config.small_model}")
        print(f"  Claude sonnet/opus models -> {config.big_model}")
        sys.exit(0)

    # Configuration summary
    print("🚀 Claude-to-OpenAI API Proxy v1.0.0")
    print(f"✅ Configuration loaded successfully")
    print(f"   OpenAI Base URL: {config.openai_base_url}")
    print(f"   Big Model (sonnet/opus): {config.big_model}")
    print(f"   Small Model (haiku): {config.small_model}")
    print(f"   Max Tokens Limit: {config.max_tokens_limit}")
    print(f"   Default Max Tokens: {config.default_max_tokens}")
    print(f"   Request Timeout: {config.request_timeout}s")
    print(f"   Server: {config.host}:{config.port}")
    print("")

    # Start server
    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=True,
    )


if __name__ == "__main__":
    main()
