#!/usr/bin/env python3
"""
Demo script showing DEFAULT_MAX_TOKENS functionality.
"""

import requests
import json
import time

def demo_default_max_tokens():
    """Demonstrate the DEFAULT_MAX_TOKENS feature with real requests."""

    base_url = "http://localhost:8082"

    print("🎯 DEFAULT_MAX_TOKENS Feature Demo")
    print("=" * 50)
    print("This demo shows how the proxy handles different max_tokens values")
    print("Make sure the proxy server is running with DEFAULT_MAX_TOKENS=1024")
    print("")

    # Test cases
    test_cases = [
        {
            "name": "Normal Request (max_tokens: 512)",
            "description": "Should preserve the requested max_tokens value",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Say hello briefly"}],
                "max_tokens": 512
            },
            "expected_behavior": "Uses requested 512 tokens"
        },
        {
            "name": "Invalid Request (max_tokens: 0)",
            "description": "Should use DEFAULT_MAX_TOKENS instead",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Say hello briefly"}],
                "max_tokens": 0
            },
            "expected_behavior": "Uses DEFAULT_MAX_TOKENS (1024) instead of 0"
        },
        {
            "name": "Small Request (max_tokens: 50)",
            "description": "Should use DEFAULT_MAX_TOKENS due to MIN_TOKENS_LIMIT",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Say hello briefly"}],
                "max_tokens": 50
            },
            "expected_behavior": "Uses DEFAULT_MAX_TOKENS (1024) as 50 < MIN_TOKENS_LIMIT"
        },
        {
            "name": "Large Request (max_tokens: 8192)",
            "description": "Should be clamped to MAX_TOKENS_LIMIT",
            "request": {
                "model": "claude-3-haiku",
                "messages": [{"role": "user", "content": "Say hello briefly"}],
                "max_tokens": 8192
            },
            "expected_behavior": "Clamped to MAX_TOKENS_LIMIT (4096) regardless of DEFAULT_MAX_TOKENS"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}: {test_case['name']}")
        print(f"📝 Description: {test_case['description']}")
        print(f"🎯 Expected: {test_case['expected_behavior']}")
        print()

        print("📤 Request payload:")
        print(json.dumps(test_case['request'], indent=2))
        print()

        try:
            # Send request to proxy
            response = requests.post(
                f"{base_url}/v1/messages",
                json=test_case['request'],
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Request successful!")
                print(f"📥 Response type: {result.get('type', 'unknown')}")
                print(f"🎯 Model used: {result.get('model', 'unknown')}")

                # Show usage if available
                if 'usage' in result:
                    print(f"📊 Token usage: {result['usage']}")

                # Show first part of content
                if 'content' in result and result['content']:
                    content = result['content'][0].get('text', '')[:100]
                    print(f"💬 Response preview: {content}...")

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
        time.sleep(1)

    print("📋 Summary:")
    print("🔒 MAX_TOKENS_LIMIT vs 🔄 DEFAULT_MAX_TOKENS:")
    print("• MAX_TOKENS_LIMIT=4096: 上限控制 - 所有请求都不能超过此值")
    print("• DEFAULT_MAX_TOKENS=1024: 默认替代 - 仅当请求值无效时使用")
    print("• MIN_TOKENS_LIMIT=100: 下限控制 - 确保最小token数量")
    print("")
    print("💡 处理逻辑:")
    print("1. 检查请求值是否有效 (>0 且 >=MIN_TOKENS_LIMIT)")
    print("2. 无效时用DEFAULT_MAX_TOKENS替代，有效时保留原值")
    print("3. 最后确保结果在[MIN_TOKENS_LIMIT, MAX_TOKENS_LIMIT]范围内")
    print("")
    print("🎯 实际应用:")
    print("• 控制成本: MAX_TOKENS_LIMIT防止过量消耗")
    print("• 避免错误: DEFAULT_MAX_TOKENS处理无效请求")
    print("• 保证质量: MIN_TOKENS_LIMIT确保响应完整")

if __name__ == "__main__":
    demo_default_max_tokens()
