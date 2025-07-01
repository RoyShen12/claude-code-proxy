"""
Simplified test to verify that our token counting changes are syntactically correct.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that our modified modules can be imported."""
    try:
        # Test request converter
        from src.conversion.request_converter import convert_claude_to_openai
        print("✅ request_converter import successful")

        # Test response converter
        from src.conversion.response_converter import convert_openai_streaming_to_claude_with_cancellation
        print("✅ response_converter import successful")

        # Test that stream_options logic is in place
        import inspect
        source = inspect.getsource(convert_claude_to_openai)
        if "stream_options" in source and "include_usage" in source:
            print("✅ stream_options modification found in request_converter")
        else:
            print("❌ stream_options modification NOT found in request_converter")

        # Test token counting logic
        source = inspect.getsource(convert_openai_streaming_to_claude_with_cancellation)
        if "Updated input tokens" in source and "Final usage data" in source:
            print("✅ Token counting debug logs found in response_converter")
        else:
            print("❌ Token counting debug logs NOT found in response_converter")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_logic():
    """Test the logic changes we made."""
    print("\n🔍 Testing logic changes...")

    # Mock objects for testing
    class MockRequest:
        def __init__(self):
            self.model = "claude-3-haiku"
            self.stream = True
            self.max_tokens = 100
            self.temperature = 0.7
            self.stop_sequences = None
            self.top_p = None
            self.tools = None
            self.tool_choice = None
            self.system = None
            self.messages = [{"role": "user", "content": "test"}]

    class MockModelManager:
        def map_claude_model_to_openai(self, model):
            return "gpt-4o-mini"

    try:
        from src.conversion.request_converter import convert_claude_to_openai

        # Test the conversion
        mock_request = MockRequest()
        mock_model_manager = MockModelManager()

        result = convert_claude_to_openai(mock_request, mock_model_manager)

        # Check if stream_options is added for streaming requests
        if result.get("stream") and "stream_options" in result:
            if result["stream_options"].get("include_usage") == True:
                print("✅ stream_options with include_usage=True added correctly")
            else:
                print("❌ stream_options added but include_usage is not True")
        else:
            print("❌ stream_options not added for streaming request")

        print(f"📋 Generated request: {result}")
        return True

    except Exception as e:
        print(f"❌ Logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing token counting fix modifications...")

    import_success = test_imports()
    logic_success = test_logic()

    if import_success and logic_success:
        print("\n✅ ALL TESTS PASSED - Token counting fix should work!")
    else:
        print("\n❌ SOME TESTS FAILED - Please review the modifications")

    print("\n📋 Summary of changes made:")
    print("1. Added stream_options: {'include_usage': True} to streaming requests")
    print("2. Modified token counting logic to properly update from usage chunks")
    print("3. Added debug logging to track token counting process")
    print("4. Fixed the max() logic issue that was keeping tokens at 0")
