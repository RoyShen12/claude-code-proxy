#!/usr/bin/env python3
"""
演示 Token Usage Logging 功能
展示如何在console中查看token使用情况
"""

import json
import sys
from pathlib import Path

def demonstrate_token_logging():
    """演示token logging功能的配置和效果"""

    print("🎯 Token Usage Logging 功能演示")
    print("=" * 60)

    print("📋 功能说明:")
    print("• 当下游API返回token usage信息时，代理会在console输出INFO级别日志")
    print("• 支持streaming和non-streaming两种请求类型")
    print("• 显示模型映射、输入输出token数量和总计")
    print("")

    print("⚙️ 配置要求:")
    print("1. 设置 LOG_LEVEL=INFO 或 LOG_LEVEL=DEBUG")
    print("2. 确保下游API支持返回usage信息")
    print("3. 对于streaming请求，需要 stream_options: {include_usage: true}")
    print("")

    print("🔧 .env 配置示例:")
    print("```")
    print("LOG_LEVEL=INFO")
    print("DEFAULT_MAX_TOKENS=1024")
    print("MAX_TOKENS_LIMIT=4096")
    print("```")
    print("")

    print("📊 Console输出示例:")
    print("```")
    print("2025-07-01 15:30:15 - INFO - 🎯 Token Usage | Model: claude-3-haiku → gpt-4o-mini | Input: 15 | Output: 42 | Total: 57")
    print("2025-07-01 15:30:20 - INFO - 🎯 Token Usage [Stream] | Model: claude-3-sonnet | Input: 23 | Output: 156 | Total: 179")
    print("2025-07-01 15:30:25 - INFO - 🎯 Token Usage [Stream+Cancel] | Model: claude-3-opus | Input: 45 | Output: 203 | Total: 248")
    print("```")
    print("")

    print("🧪 测试方法:")
    print("1. 启动代理服务器:")
    print("   python start_proxy.py")
    print("")
    print("2. 发送测试请求:")
    print("   python test_token_logging.py")
    print("")
    print("3. 观察console输出中的token usage日志")
    print("")

    print("📝 日志格式说明:")
    log_formats = [
        {
            "类型": "Non-streaming",
            "格式": "🎯 Token Usage | Model: {source} → {target} | Input: {input} | Output: {output} | Total: {total}",
            "触发": "普通API调用完成时"
        },
        {
            "类型": "Streaming",
            "格式": "🎯 Token Usage [Stream] | Model: {source} | Input: {input} | Output: {output} | Total: {total}",
            "触发": "流式API调用的最终token统计时"
        },
        {
            "类型": "Streaming+Cancel",
            "格式": "🎯 Token Usage [Stream+Cancel] | Model: {source} | Input: {input} | Output: {output} | Total: {total}",
            "触发": "支持取消的流式API调用完成时"
        }
    ]

    for fmt in log_formats:
        print(f"• {fmt['类型']}: {fmt['触发']}")
        print(f"  格式: {fmt['格式']}")
        print()

    print("💡 注意事项:")
    print("• 只有当input_tokens > 0 或 output_tokens > 0时才会记录日志")
    print("• 日志级别必须设置为INFO或DEBUG才能看到")
    print("• 如果下游API不返回usage信息，将不会有token日志")
    print("• streaming请求需要stream_options支持才能获取token信息")

    print("\n🎯 实际代码位置:")
    print("• Non-streaming: src/conversion/response_converter.py:convert_openai_to_claude_response()")
    print("• Streaming: src/conversion/response_converter.py:convert_openai_streaming_to_claude*()")

if __name__ == "__main__":
    demonstrate_token_logging()
