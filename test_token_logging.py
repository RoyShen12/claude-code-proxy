#!/usr/bin/env python3
"""
Test script to verify token usage logging functionality.
"""

import requests
import json
import time

def test_token_logging():
    """Test token usage logging with different request types."""

    base_url = "http://localhost:8082"

    print("🎯 Token Usage Logging Test")
    print("=" * 50)
    print("This test verifies that token usage is logged to console with INFO level")
    print("Make sure the proxy server is running with LOG_LEVEL=INFO")
    print("")

    # Test cases
    test_cases = [
        {
            "name": "Non-Streaming Request",
            "description": "Test token logging for regular API calls",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Count from 1 to 5"}],
                "max_tokens": 100,
                "stream": False
            }
        },
        {
            "name": "Streaming Request",
            "description": "Test token logging for streaming API calls",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Say hello and introduce yourself"}],
                "max_tokens": 150,
                "stream": True
            }
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}: {test_case['name']}")
        print(f"📝 Description: {test_case['description']}")
        print()

        print("📤 Request:")
        print(json.dumps(test_case['request'], indent=2))
        print()

        try:
            # Send request to proxy
            response = requests.post(
                f"{base_url}/v1/messages",
                json=test_case['request'],
                headers={"Content-Type": "application/json"},
                timeout=30,
                stream=test_case['request'].get('stream', False)
            )

            if response.status_code == 200:
                print("✅ Request successful!")

                if test_case['request'].get('stream', False):
                    print("📡 Processing streaming response...")
                    # Process streaming response
                    total_chunks = 0
                    for line in response.iter_lines():
                        if line:
                            total_chunks += 1
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data = line_str[6:]
                                if data.strip() == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data)
                                    if chunk.get('type') == 'message_delta' and 'usage' in chunk:
                                        print(f"📊 Final usage in stream: {chunk['usage']}")
                                except:
                                    pass
                    print(f"📡 Processed {total_chunks} streaming chunks")
                else:
                    # Process regular response
                    result = response.json()
                    print(f"📥 Response type: {result.get('type', 'unknown')}")
                    if 'usage' in result:
                        print(f"📊 Token usage: {result['usage']}")

            else:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"🔍 Error: {response.text}")

        except requests.exceptions.ConnectionError:
            print("❌ Connection failed - Make sure the proxy server is running on localhost:8082")
        except Exception as e:
            print(f"❌ Error: {e}")

        print()
        print("-" * 50)
        print()

        # Small delay between requests
        time.sleep(2)

    print("📋 Expected Console Output:")
    print("You should see INFO level logs in the proxy server console like:")
    print("• 🎯 Token Usage | Model: claude-3-haiku → gpt-4o-mini | Input: X | Output: Y | Total: Z")
    print("• 🎯 Token Usage [Stream] | Model: claude-3-haiku | Input: X | Output: Y | Total: Z")
    print("")
    print("💡 If you don't see these logs, check that LOG_LEVEL=INFO in your .env file")

if __name__ == "__main__":
    test_token_logging()
