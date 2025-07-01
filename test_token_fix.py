#!/usr/bin/env python3
"""
Test script to verify token counting fix in streaming responses.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.core.config import config
from src.core.client import OpenAIClient

async def test_streaming_token_count():
    """Test streaming response to verify token counting works."""

    # Ensure we have debug logging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    try:
        # Create OpenAI client
        client = OpenAIClient(
            config.openai_api_key,
            config.openai_base_url,
            config.request_timeout,
            api_version=config.azure_api_version,
        )

        # Test request with stream_options
        test_request = {
            "model": config.small_model,
            "messages": [
                {"role": "user", "content": "Hello! Please count to 5."}
            ],
            "max_tokens": 100,
            "stream": True,
            "stream_options": {"include_usage": True}
        }

        logger.info(f"Testing streaming with request: {json.dumps(test_request, indent=2)}")
        logger.info("Starting streaming test...")

        # Test streaming
        chunk_count = 0
        usage_chunks = 0
        final_usage = None

        async for chunk_data in client.create_chat_completion_stream(test_request, "test_request"):
            chunk_count += 1

            if chunk_data.startswith("data: "):
                chunk_json = chunk_data[6:]
                if chunk_json.strip() == "[DONE]":
                    logger.info("Received [DONE] chunk")
                    break

                try:
                    chunk = json.loads(chunk_json)
                    usage = chunk.get("usage")

                    if usage:
                        usage_chunks += 1
                        final_usage = usage
                        logger.info(f"Chunk {chunk_count} - Usage found: {usage}")
                    else:
                        logger.debug(f"Chunk {chunk_count} - No usage data")

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse chunk {chunk_count}: {e}")

        # Report results
        logger.info(f"\n=== Test Results ===")
        logger.info(f"Total chunks received: {chunk_count}")
        logger.info(f"Chunks with usage data: {usage_chunks}")
        logger.info(f"Final usage: {final_usage}")

        if final_usage and final_usage.get("completion_tokens", 0) > 0:
            logger.info("✅ SUCCESS: Token counting is working!")
            return True
        else:
            logger.error("❌ FAILURE: Token counting still returning 0")
            return False

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🧪 Testing stream token counting fix...")
    result = asyncio.run(test_streaming_token_count())
    sys.exit(0 if result else 1)
