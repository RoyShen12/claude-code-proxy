import json
import uuid
import logging
from fastapi import HTTPException, Request
from src.core.constants import Constants
from src.core.token_estimator import (
    estimate_input_tokens, 
    estimate_output_tokens, 
    should_use_estimation
)
from src.core.config import config
from src.models.claude import ClaudeMessagesRequest

logger = logging.getLogger(__name__)


def convert_openai_to_claude_response(
    openai_response: dict, original_request: ClaudeMessagesRequest
) -> dict:
    """Convert OpenAI response to Claude format."""

    # Extract response data
    choices = openai_response.get("choices", [])
    if not choices:
        raise HTTPException(status_code=500, detail="No choices in OpenAI response")

    choice = choices[0]
    message = choice.get("message", {})

    # Build Claude content blocks
    content_blocks = []

    # Add text content
    text_content = message.get("content")
    if text_content:
        content_blocks.append({"type": Constants.CONTENT_TEXT, "text": text_content})

    # Add tool calls
    tool_calls = message.get("tool_calls", []) or []
    for tool_call in tool_calls:
        if tool_call.get("type") == Constants.TOOL_FUNCTION:
            function_data = tool_call.get(Constants.TOOL_FUNCTION, {})
            try:
                arguments = json.loads(function_data.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {"raw_arguments": function_data.get("arguments", "")}

            content_blocks.append(
                {
                    "type": Constants.CONTENT_TOOL_USE,
                    "id": tool_call.get("id", f"tool_{uuid.uuid4()}"),
                    "name": function_data.get("name", ""),
                    "input": arguments,
                }
            )

    # Ensure at least one content block
    if not content_blocks:
        content_blocks.append({"type": Constants.CONTENT_TEXT, "text": ""})

    # Map finish reason
    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = {
        "stop": Constants.STOP_END_TURN,
        "length": Constants.STOP_MAX_TOKENS,
        "tool_calls": Constants.STOP_TOOL_USE,
        "function_call": Constants.STOP_TOOL_USE,
    }.get(finish_reason, Constants.STOP_END_TURN)

    # Get usage data from OpenAI response
    usage_data = openai_response.get("usage", {})
    input_tokens = usage_data.get("prompt_tokens", 0)
    output_tokens = usage_data.get("completion_tokens", 0)
    
    # Use token estimation if enabled and downstream API doesn't provide accurate usage
    if config.enable_token_estimation and should_use_estimation(usage_data):
        logger.debug("Downstream API usage data is incomplete, using token estimation")
        
        # Estimate input tokens from original request
        estimated_input = estimate_input_tokens(original_request)
        
        # Estimate output tokens from response content
        response_text = ""
        for block in content_blocks:
            if block.get("type") == Constants.CONTENT_TEXT:
                response_text += block.get("text", "")
        estimated_output = estimate_output_tokens(response_text)
        
        input_tokens = estimated_input
        output_tokens = estimated_output
        
        logger.info(f"📊 Using estimated tokens - Input: {input_tokens}, Output: {output_tokens}")

    # Build Claude response
    claude_response = {
        "id": openai_response.get("id", f"msg_{uuid.uuid4()}"),
        "type": "message",
        "role": Constants.ROLE_ASSISTANT,
        "model": original_request.model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }

    # Log token usage info to console
    input_tokens = claude_response["usage"]["input_tokens"]
    output_tokens = claude_response["usage"]["output_tokens"]
    # Always log token usage for debugging, even if tokens are 0
    logger.info(f"🎯 Token Usage | Model: {original_request.model} → {openai_response.get('model', 'unknown')} | Input: {input_tokens} | Output: {output_tokens} | Total: {input_tokens + output_tokens}")

    return claude_response


async def convert_openai_streaming_to_claude(
    openai_stream, original_request: ClaudeMessagesRequest, logger
):
    """Convert OpenAI streaming response to Claude streaming format."""

    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # Send initial SSE events
    yield f"event: {Constants.EVENT_MESSAGE_START}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_START, 'message': {'id': message_id, 'type': 'message', 'role': Constants.ROLE_ASSISTANT, 'model': original_request.model, 'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': 0, 'content_block': {'type': Constants.CONTENT_TEXT, 'text': ''}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_PING}\ndata: {json.dumps({'type': Constants.EVENT_PING}, ensure_ascii=False)}\n\n"

    # Process streaming chunks
    text_block_index = 0
    tool_block_counter = 0
    current_tool_calls = {}
    final_stop_reason = Constants.STOP_END_TURN

    # Track token usage from OpenAI streaming response
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async for line in openai_stream:
            if line.strip():
                # Decode bytes to string if needed
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(chunk_data)
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        # Extract token usage information from chunk if available
                        usage = chunk.get("usage", {})
                        if usage:
                            # Update token counts when usage information is available
                            if "prompt_tokens" in usage and usage["prompt_tokens"] > 0:
                                total_input_tokens = usage["prompt_tokens"]
                                logger.debug(f"[Basic Stream] Updated input tokens: {total_input_tokens}")
                            if "completion_tokens" in usage and usage["completion_tokens"] > 0:
                                total_output_tokens = usage["completion_tokens"]
                                logger.debug(f"[Basic Stream] Updated output tokens: {total_output_tokens}")

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse chunk: {chunk_data}, error: {e}"
                        )
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Handle text delta
                    if "content" in delta and delta["content"]:
                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': text_block_index, 'delta': {'type': Constants.DELTA_TEXT, 'text': delta['content']}}, ensure_ascii=False)}\n\n"

                    # Handle tool call deltas with improved incremental processing
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            tc_index = tc_delta.get("index", 0)

                            # Initialize tool call tracking by index if not exists
                            if tc_index not in current_tool_calls:
                                current_tool_calls[tc_index] = {
                                    "id": None,
                                    "name": None,
                                    "args_buffer": "",
                                    "json_sent": False,
                                    "claude_index": None,
                                    "started": False
                                }

                            tool_call = current_tool_calls[tc_index]

                            # Update tool call ID if provided
                            if tc_delta.get("id"):
                                tool_call["id"] = tc_delta["id"]

                            # Update function name and start content block if we have both id and name
                            function_data = tc_delta.get(Constants.TOOL_FUNCTION, {})
                            if function_data.get("name"):
                                tool_call["name"] = function_data["name"]

                            # Start content block when we have complete initial data
                            if (tool_call["id"] and tool_call["name"] and not tool_call["started"]):
                                tool_block_counter += 1
                                claude_index = text_block_index + tool_block_counter
                                tool_call["claude_index"] = claude_index
                                tool_call["started"] = True

                                yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': claude_index, 'content_block': {'type': Constants.CONTENT_TOOL_USE, 'id': tool_call['id'], 'name': tool_call['name'], 'input': {}}}, ensure_ascii=False)}\n\n"

                            # Handle function arguments
                            if "arguments" in function_data and tool_call["started"]:
                                tool_call["args_buffer"] += function_data["arguments"]

                                # Try to parse complete JSON and send delta when we have valid JSON
                                try:
                                    json.loads(tool_call["args_buffer"])
                                    # If parsing succeeds and we haven't sent this JSON yet
                                    if not tool_call["json_sent"]:
                                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': tool_call['claude_index'], 'delta': {'type': Constants.DELTA_INPUT_JSON, 'partial_json': tool_call['args_buffer']}}, ensure_ascii=False)}\n\n"
                                        tool_call["json_sent"] = True
                                except json.JSONDecodeError:
                                    # JSON is incomplete, continue accumulating
                                    pass

                    # Handle finish reason
                    if finish_reason:
                        if finish_reason == "length":
                            final_stop_reason = Constants.STOP_MAX_TOKENS
                        elif finish_reason in ["tool_calls", "function_call"]:
                            final_stop_reason = Constants.STOP_TOOL_USE
                        elif finish_reason == "stop":
                            final_stop_reason = Constants.STOP_END_TURN
                        else:
                            final_stop_reason = Constants.STOP_END_TURN
                        break

    except Exception as e:
        # Handle any streaming errors gracefully
        logger.error(f"Streaming error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        error_event = {
            "type": "error",
            "error": {"type": "api_error", "message": f"Streaming error: {str(e)}"},
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        return

    # Send final SSE events
    yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': text_block_index}, ensure_ascii=False)}\n\n"

    for tool_data in current_tool_calls.values():
        if tool_data.get("started") and tool_data.get("claude_index") is not None:
            yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': tool_data['claude_index']}, ensure_ascii=False)}\n\n"

    # Apply token estimation if enabled and usage data is incomplete
    if config.enable_token_estimation and total_input_tokens == 0 and total_output_tokens == 0:
        logger.debug("Downstream API usage data is incomplete, using token estimation for basic streaming")
        
        # Estimate input tokens from original request
        estimated_input = estimate_input_tokens(original_request)
        
        # For streaming, we need to estimate output tokens from accumulated text
        # Note: This is a rough estimate since we don't store all the streamed text
        # We'll use a conservative estimate based on the request's max_tokens
        max_tokens = getattr(original_request, 'max_tokens', 1024)
        estimated_output = min(max_tokens // 4, 50)  # Conservative estimate: 1/4 of max_tokens or 50, whichever is smaller
        
        total_input_tokens = estimated_input
        total_output_tokens = estimated_output
        
        logger.info(f"📊 Using estimated tokens for basic streaming - Input: {total_input_tokens}, Output: {total_output_tokens} (conservative estimate)")

    usage_data = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
    logger.debug(f"[Basic Stream] Final usage data: {usage_data}")

    # Log token usage info to console for streaming
    # Always log token usage for debugging, even if tokens are 0
    print(f"🔥 DEBUG: Stream Token Usage - Input: {total_input_tokens}, Output: {total_output_tokens}", flush=True)
    logger.info(f"🎯 Token Usage [Stream] | Model: {original_request.model} | Input: {total_input_tokens} | Output: {total_output_tokens} | Total: {total_input_tokens + total_output_tokens}")

    yield f"event: {Constants.EVENT_MESSAGE_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_DELTA, 'delta': {'stop_reason': final_stop_reason, 'stop_sequence': None}, 'usage': usage_data}, ensure_ascii=False)}\n\n"
    yield f"event: {Constants.EVENT_MESSAGE_STOP}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_STOP}, ensure_ascii=False)}\n\n"


async def convert_openai_streaming_to_claude_with_cancellation(
    openai_stream,
    original_request: ClaudeMessagesRequest,
    logger,
    http_request: Request,
    openai_client,
    request_id: str,
):
    """Convert OpenAI streaming response to Claude streaming format with cancellation support."""

    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # Send initial SSE events
    yield f"event: {Constants.EVENT_MESSAGE_START}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_START, 'message': {'id': message_id, 'type': 'message', 'role': Constants.ROLE_ASSISTANT, 'model': original_request.model, 'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': 0, 'content_block': {'type': Constants.CONTENT_TEXT, 'text': ''}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_PING}\ndata: {json.dumps({'type': Constants.EVENT_PING}, ensure_ascii=False)}\n\n"

    # Process streaming chunks
    text_block_index = 0
    tool_block_counter = 0
    current_tool_calls = {}
    final_stop_reason = Constants.STOP_END_TURN

    # Track token usage from OpenAI streaming response
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async for line in openai_stream:
            # Check if client disconnected
            if await http_request.is_disconnected():
                logger.info(f"Client disconnected, cancelling request {request_id}")
                openai_client.cancel_request(request_id)
                break

            if line.strip():
                # Decode bytes to string if needed
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(chunk_data)

                        # Check for error data from the client
                        if "error" in chunk:
                            error_info = chunk["error"]
                            error_type = error_info.get("type", "unknown_error")
                            error_message = error_info.get("message", "Unknown error occurred")
                            status_code = error_info.get("status_code", 500)

                            logger.error(f"OpenAI API error: {error_type} - {error_message} (status: {status_code})")

                            # Send error event in Claude format
                            error_event = {
                                "type": "error",
                                "error": {
                                    "type": error_type,
                                    "message": error_message
                                }
                            }
                            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                            return

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        # Extract token usage information from chunk if available
                        usage = chunk.get("usage", {})
                        if usage:
                            # Update token counts when usage information is available
                            if "prompt_tokens" in usage and usage["prompt_tokens"] > 0:
                                total_input_tokens = usage["prompt_tokens"]
                                logger.debug(f"[Cancellation Stream] Updated input tokens: {total_input_tokens}")
                            if "completion_tokens" in usage and usage["completion_tokens"] > 0:
                                total_output_tokens = usage["completion_tokens"]
                                logger.debug(f"[Cancellation Stream] Updated output tokens: {total_output_tokens}")

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse chunk: {chunk_data}, error: {e}"
                        )
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Handle text delta
                    if "content" in delta and delta["content"]:
                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': text_block_index, 'delta': {'type': Constants.DELTA_TEXT, 'text': delta['content']}}, ensure_ascii=False)}\n\n"

                    # Handle tool call deltas with improved incremental processing
                    if "tool_calls" in delta and delta["tool_calls"]:
                        for tc_delta in delta["tool_calls"]:
                            tc_index = tc_delta.get("index", 0)

                            # Initialize tool call tracking by index if not exists
                            if tc_index not in current_tool_calls:
                                current_tool_calls[tc_index] = {
                                    "id": None,
                                    "name": None,
                                    "args_buffer": "",
                                    "json_sent": False,
                                    "claude_index": None,
                                    "started": False
                                }

                            tool_call = current_tool_calls[tc_index]

                            # Update tool call ID if provided
                            if tc_delta.get("id"):
                                tool_call["id"] = tc_delta["id"]

                            # Update function name and start content block if we have both id and name
                            function_data = tc_delta.get(Constants.TOOL_FUNCTION, {})
                            if function_data.get("name"):
                                tool_call["name"] = function_data["name"]

                            # Start content block when we have complete initial data
                            if (tool_call["id"] and tool_call["name"] and not tool_call["started"]):
                                tool_block_counter += 1
                                claude_index = text_block_index + tool_block_counter
                                tool_call["claude_index"] = claude_index
                                tool_call["started"] = True

                                yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': claude_index, 'content_block': {'type': Constants.CONTENT_TOOL_USE, 'id': tool_call['id'], 'name': tool_call['name'], 'input': {}}}, ensure_ascii=False)}\n\n"

                            # Handle function arguments
                            if "arguments" in function_data and tool_call["started"] and function_data["arguments"] is not None:
                                tool_call["args_buffer"] += function_data["arguments"]

                                # Try to parse complete JSON and send delta when we have valid JSON
                                try:
                                    json.loads(tool_call["args_buffer"])
                                    # If parsing succeeds and we haven't sent this JSON yet
                                    if not tool_call["json_sent"]:
                                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': tool_call['claude_index'], 'delta': {'type': Constants.DELTA_INPUT_JSON, 'partial_json': tool_call['args_buffer']}}, ensure_ascii=False)}\n\n"
                                        tool_call["json_sent"] = True
                                except json.JSONDecodeError:
                                    # JSON is incomplete, continue accumulating
                                    pass

                    # Handle finish reason
                    if finish_reason:
                        if finish_reason == "length":
                            final_stop_reason = Constants.STOP_MAX_TOKENS
                        elif finish_reason in ["tool_calls", "function_call"]:
                            final_stop_reason = Constants.STOP_TOOL_USE
                        elif finish_reason == "stop":
                            final_stop_reason = Constants.STOP_END_TURN
                        else:
                            final_stop_reason = Constants.STOP_END_TURN
                        break

    except HTTPException as e:
        # Handle cancellation
        if e.status_code == 499:
            logger.info(f"Request {request_id} was cancelled")
            error_event = {
                "type": "error",
                "error": {
                    "type": "cancelled",
                    "message": "Request was cancelled by client",
                },
            }
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            return
        else:
            raise
    except Exception as e:
        # Handle any streaming errors gracefully
        logger.error(f"Streaming error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        error_event = {
            "type": "error",
            "error": {"type": "api_error", "message": f"Streaming error: {str(e)}"},
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        return

    # Send final SSE events
    yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': text_block_index}, ensure_ascii=False)}\n\n"

    for tool_data in current_tool_calls.values():
        if tool_data.get("started") and tool_data.get("claude_index") is not None:
            yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': tool_data['claude_index']}, ensure_ascii=False)}\n\n"

    # Apply token estimation if enabled and usage data is incomplete
    if config.enable_token_estimation and total_input_tokens == 0 and total_output_tokens == 0:
        logger.debug("Downstream API usage data is incomplete, using token estimation for streaming")
        
        # Estimate input tokens from original request
        estimated_input = estimate_input_tokens(original_request)
        
        # For streaming, we need to estimate output tokens from accumulated text
        # Note: This is a rough estimate since we don't store all the streamed text
        # We'll use a conservative estimate based on the request's max_tokens
        max_tokens = getattr(original_request, 'max_tokens', 1024)
        estimated_output = min(max_tokens // 4, 50)  # Conservative estimate: 1/4 of max_tokens or 50, whichever is smaller
        
        total_input_tokens = estimated_input
        total_output_tokens = estimated_output
        
        logger.info(f"📊 Using estimated tokens for streaming - Input: {total_input_tokens}, Output: {total_output_tokens} (conservative estimate)")

    usage_data = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
    logger.debug(f"[Cancellation Stream] Final usage data: {usage_data}")

    # Log token usage info to console for streaming with cancellation
    # Always log token usage for debugging, even if tokens are 0
    logger.info(f"🎯 Token Usage [Stream+Cancel] | Model: {original_request.model} | Input: {total_input_tokens} | Output: {total_output_tokens} | Total: {total_input_tokens + total_output_tokens}")

    yield f"event: {Constants.EVENT_MESSAGE_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_DELTA, 'delta': {'stop_reason': final_stop_reason, 'stop_sequence': None}, 'usage': usage_data}, ensure_ascii=False)}\n\n"
    yield f"event: {Constants.EVENT_MESSAGE_STOP}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_STOP}, ensure_ascii=False)}\n\n"
