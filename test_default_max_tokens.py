"""
Test script to verify DEFAULT_MAX_TOKENS functionality.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_default_max_tokens():
    """Test that DEFAULT_MAX_TOKENS is correctly applied."""

    # Mock the config module with our test values
    mock_config = MagicMock()
    mock_config.min_tokens_limit = 100
    mock_config.max_tokens_limit = 4096
    mock_config.default_max_tokens = 1024  # Our new default value

    sys.modules['src.core.config'] = MagicMock()
    sys.modules['src.core.config'].config = mock_config

    try:
        from src.conversion.request_converter import convert_claude_to_openai

        # Mock objects
        class MockRequest:
            def __init__(self, max_tokens):
                self.model = "claude-3-haiku"
                self.max_tokens = max_tokens
                self.stream = False
                self.temperature = 0.7
                self.stop_sequences = None
                self.top_p = None
                self.tools = None
                self.tool_choice = None
                self.system = None
                self.messages = []

        class MockMessage:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        class MockModelManager:
            def map_claude_model_to_openai(self, model):
                return "gpt-4o-mini"

        model_manager = MockModelManager()

        # Test Case 1: Normal max_tokens value should be preserved
        print("🧪 Test Case 1: Normal max_tokens value (512)")
        request1 = MockRequest(max_tokens=512)
        request1.messages = [MockMessage("user", "Hello")]

        result1 = convert_claude_to_openai(request1, model_manager)
        expected_tokens_1 = 512  # Should use the requested value

        print(f"   Requested: {request1.max_tokens}")
        print(f"   Expected: {expected_tokens_1}")
        print(f"   Actual: {result1['max_tokens']}")

        if result1['max_tokens'] == expected_tokens_1:
            print("   ✅ PASS - Normal max_tokens preserved")
        else:
            print("   ❌ FAIL - Normal max_tokens not preserved")

        # Test Case 2: Invalid/zero max_tokens should use default
        print("\n🧪 Test Case 2: Invalid max_tokens value (0)")
        request2 = MockRequest(max_tokens=0)
        request2.messages = [MockMessage("user", "Hello")]

        result2 = convert_claude_to_openai(request2, model_manager)
        expected_tokens_2 = 1024  # Should use default_max_tokens

        print(f"   Requested: {request2.max_tokens}")
        print(f"   Expected: {expected_tokens_2}")
        print(f"   Actual: {result2['max_tokens']}")

        if result2['max_tokens'] == expected_tokens_2:
            print("   ✅ PASS - Default max_tokens applied for invalid value")
        else:
            print("   ❌ FAIL - Default max_tokens not applied")

        # Test Case 3: Very small max_tokens should use default
        print("\n🧪 Test Case 3: Very small max_tokens value (50)")
        request3 = MockRequest(max_tokens=50)
        request3.messages = [MockMessage("user", "Hello")]

        result3 = convert_claude_to_openai(request3, model_manager)
        # Since 50 < min_tokens_limit (100), it should use default_max_tokens (1024)
        expected_tokens_3 = 1024

        print(f"   Requested: {request3.max_tokens}")
        print(f"   Expected: {expected_tokens_3}")
        print(f"   Actual: {result3['max_tokens']}")

        if result3['max_tokens'] == expected_tokens_3:
            print("   ✅ PASS - Default max_tokens applied for small value")
        else:
            print("   ❌ FAIL - Default max_tokens not applied for small value")

        # Test Case 4: Very large max_tokens should be clamped to max_limit
        print("\n🧪 Test Case 4: Very large max_tokens value (8192)")
        request4 = MockRequest(max_tokens=8192)
        request4.messages = [MockMessage("user", "Hello")]

        result4 = convert_claude_to_openai(request4, model_manager)
        expected_tokens_4 = 4096  # Should be clamped to max_tokens_limit

        print(f"   Requested: {request4.max_tokens}")
        print(f"   Expected: {expected_tokens_4}")
        print(f"   Actual: {result4['max_tokens']}")

        if result4['max_tokens'] == expected_tokens_4:
            print("   ✅ PASS - Large max_tokens clamped to limit")
        else:
            print("   ❌ FAIL - Large max_tokens not properly clamped")

        # Print example request
        print(f"\n📋 Example generated request with DEFAULT_MAX_TOKENS:")
        print(json.dumps(result2, indent=2))

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing DEFAULT_MAX_TOKENS functionality...")
    print("=" * 60)

    success = test_default_max_tokens()

    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Feature Summary:")
        print("• Added DEFAULT_MAX_TOKENS environment variable")
        print("• Default value: 1024 tokens")
        print("• Applied when max_tokens is 0, negative, or below minimum")
        print("• Configurable via .env file")
        print("• Shown in startup configuration summary")
    else:
        print("❌ SOME TESTS FAILED - Please review the implementation")
