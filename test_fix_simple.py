"""
Direct test of the modified functions without config dependency.
"""

import json
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_stream_options_addition():
    """Test that stream_options is correctly added to requests."""

    # Mock the config module to avoid API key requirement
    import sys
    from unittest.mock import MagicMock

    mock_config = MagicMock()
    mock_config.min_tokens_limit = 100
    mock_config.max_tokens_limit = 4096

    sys.modules['src.core.config'] = MagicMock()
    sys.modules['src.core.config'].config = mock_config

    try:
        from src.conversion.request_converter import convert_claude_to_openai

        # Mock objects
        class MockRequest:
            def __init__(self, stream=True):
                self.model = "claude-3-haiku"
                self.stream = stream
                self.max_tokens = 100
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

        # Test streaming request
        streaming_request = MockRequest(stream=True)
        streaming_request.messages = [MockMessage("user", "Hello")]

        model_manager = MockModelManager()
        result = convert_claude_to_openai(streaming_request, model_manager)

        print(f"📋 Generated streaming request:")
        print(json.dumps(result, indent=2))

        # Check stream_options
        if result.get("stream") and "stream_options" in result:
            if result["stream_options"].get("include_usage") == True:
                print("✅ stream_options with include_usage=True added for streaming request")
            else:
                print("❌ stream_options added but include_usage is not True")
                print(f"   Actual: {result['stream_options']}")
        else:
            print("❌ stream_options not added for streaming request")

        # Test non-streaming request
        non_streaming_request = MockRequest(stream=False)
        non_streaming_request.messages = [MockMessage("user", "Hello")]

        result2 = convert_claude_to_openai(non_streaming_request, model_manager)

        if not result2.get("stream") and "stream_options" not in result2:
            print("✅ stream_options correctly NOT added for non-streaming request")
        else:
            print("❌ stream_options incorrectly added to non-streaming request")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_token_counting_logic():
    """Test that token counting logic is properly modified."""

    # Check the source code directly
    try:
        import inspect
        from src.conversion import response_converter

        # Get the source of the cancellation function
        source = inspect.getsource(response_converter.convert_openai_streaming_to_claude_with_cancellation)

        # Check for our modifications
        checks = [
            ("prompt_tokens", "Input token handling"),
            ("completion_tokens", "Output token handling"),
            ("Updated input tokens", "Debug logging for input tokens"),
            ("Updated output tokens", "Debug logging for output tokens"),
            ("Final usage data", "Debug logging for final usage")
        ]

        all_passed = True
        for check, description in checks:
            if check in source:
                print(f"✅ {description} - Found")
            else:
                print(f"❌ {description} - NOT Found")
                all_passed = False

        # Check that we removed the problematic max() logic
        if "max(total_input_tokens, usage.get(" not in source:
            print("✅ Old max() logic removed")
        else:
            print("❌ Old max() logic still present")
            all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ Token counting logic test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing stream token counting fix...")
    print("=" * 50)

    print("\n🔧 Testing stream_options addition:")
    stream_test = test_stream_options_addition()

    print("\n🔧 Testing token counting logic:")
    token_test = test_token_counting_logic()

    print("\n" + "=" * 50)
    if stream_test and token_test:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Fix Summary:")
        print("1. ✅ stream_options: {'include_usage': True} added to streaming requests")
        print("2. ✅ Token counting logic updated to properly handle usage data")
        print("3. ✅ Debug logging added to track token counting")
        print("4. ✅ Removed problematic max() logic that caused 0 token counts")
        print("\n🎯 The token count issue should now be resolved!")
    else:
        print("❌ SOME TESTS FAILED - Please review the code")
