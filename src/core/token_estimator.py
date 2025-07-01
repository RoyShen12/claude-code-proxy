"""
Token estimation utilities for when downstream APIs don't provide accurate usage data.

This module provides rough token count estimation based on text analysis.
"""

import re
from typing import List, Dict, Any
from src.models.claude import ClaudeMessagesRequest


class TokenEstimator:
    """估算token使用量的工具类"""
    
    def __init__(self):
        # 基于经验的token估算比例
        self.ENGLISH_CHAR_PER_TOKEN = 4.0  # 英文大约4个字符=1个token
        self.CHINESE_CHAR_PER_TOKEN = 1.2  # 中文大约1.2个字符=1个token（中文token更复杂）
        self.MIXED_CHAR_PER_TOKEN = 2.5    # 中英混合文本的平均值
        
    def estimate_text_tokens(self, text) -> int:
        """
        估算文本的token数量
        
        Args:
            text: 要估算的文本，可以是字符串或包含text的对象列表
            
        Returns:
            估算的token数量
        """
        if not text:
            return 0
        
        # 处理不同类型的text参数
        if isinstance(text, str):
            text_content = text
        elif isinstance(text, list):
            # 如果是列表，提取所有text内容
            text_content = ""
            for item in text:
                if isinstance(item, dict) and 'text' in item:
                    text_content += item['text'] + " "
                elif hasattr(item, 'text'):
                    text_content += item.text + " "
                elif isinstance(item, str):
                    text_content += item + " "
            text_content = text_content.strip()
        else:
            # 尝试获取text属性
            if hasattr(text, 'text'):
                text_content = text.text
            else:
                text_content = str(text)
        
        if not text_content:
            return 0
            
        # 分析文本的中英文比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text_content))
        total_chars = len(text_content)
        
        if total_chars == 0:
            return 0
            
        chinese_ratio = chinese_chars / total_chars
        
        # 根据中英文比例选择估算方法
        if chinese_ratio > 0.7:  # 主要是中文
            estimated_tokens = total_chars / self.CHINESE_CHAR_PER_TOKEN
        elif chinese_ratio < 0.1:  # 主要是英文
            estimated_tokens = total_chars / self.ENGLISH_CHAR_PER_TOKEN
        else:  # 中英混合
            estimated_tokens = total_chars / self.MIXED_CHAR_PER_TOKEN
            
        return max(1, int(estimated_tokens))  # 至少1个token
    
    def estimate_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        估算消息列表的token数量
        
        Args:
            messages: 消息列表
            
        Returns:
            估算的总token数量
        """
        total_tokens = 0
        
        for message in messages:
            # 估算role字段的token (通常很少)
            if 'role' in message:
                total_tokens += 1  # role字段大约1个token
                
            # 估算content字段的token
            if 'content' in message:
                content = message['content']
                if isinstance(content, str):
                    total_tokens += self.estimate_text_tokens(content)
                elif isinstance(content, list):
                    # Claude format中content可能是数组
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            total_tokens += self.estimate_text_tokens(item['text'])
                        elif isinstance(item, str):
                            total_tokens += self.estimate_text_tokens(item)
        
        # 加上一些额外的开销token（消息格式、分隔符等）
        overhead_tokens = len(messages) * 3  # 每条消息大约3个额外token
        total_tokens += overhead_tokens
        
        return max(1, total_tokens)
    
    def estimate_request_input_tokens(self, request: ClaudeMessagesRequest) -> int:
        """
        估算请求的输入token数量
        
        Args:
            request: Claude请求对象
            
        Returns:
            估算的输入token数量
        """
        total_tokens = 0
        
        # 估算messages的token
        if hasattr(request, 'messages') and request.messages:
            messages_dict = [msg.dict() if hasattr(msg, 'dict') else msg for msg in request.messages]
            total_tokens += self.estimate_messages_tokens(messages_dict)
        
        # 估算system prompt的token
        if hasattr(request, 'system') and request.system:
            total_tokens += self.estimate_text_tokens(request.system)
            
        # 加上模型名称等元数据的token
        total_tokens += 5  # 模型名称、参数等大约5个token
        
        return max(1, total_tokens)
    
    def estimate_completion_tokens(self, text: str) -> int:
        """
        估算完成文本的token数量
        
        Args:
            text: 完成的文本内容
            
        Returns:
            估算的输出token数量
        """
        return self.estimate_text_tokens(text)


# 全局token估算器实例
token_estimator = TokenEstimator()


def estimate_input_tokens(request: ClaudeMessagesRequest) -> int:
    """估算输入token数量的便捷函数"""
    return token_estimator.estimate_request_input_tokens(request)


def estimate_output_tokens(text: str) -> int:
    """估算输出token数量的便捷函数"""
    return token_estimator.estimate_completion_tokens(text)


def should_use_estimation(usage_data: Dict[str, Any]) -> bool:
    """
    判断是否应该使用token估算
    
    Args:
        usage_data: 下游API返回的usage数据
        
    Returns:
        是否应该使用估算
    """
    if not usage_data:
        return True
        
    # 如果input_tokens和output_tokens都是0，可能是API不支持或有问题
    input_tokens = usage_data.get('prompt_tokens', usage_data.get('input_tokens', 0))
    output_tokens = usage_data.get('completion_tokens', usage_data.get('output_tokens', 0))
    
    return input_tokens == 0 and output_tokens == 0
