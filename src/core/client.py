import asyncio
import json
from fastapi import HTTPException
from typing import Optional, AsyncGenerator, Dict, Any
from openai import AsyncOpenAI, AsyncAzureOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai._exceptions import APIError, RateLimitError, AuthenticationError, BadRequestError

class OpenAIClient:
    """Async OpenAI client with cancellation support."""
    
    def __init__(self, api_key: str, base_url: str, timeout: int = 90, api_version: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version  # Store API version for later use
        
        # Detect if using Azure and instantiate the appropriate client
        if api_version:
            # For Azure OpenAI, we need to ensure we have the correct endpoint format
            azure_endpoint = base_url
            
            # Clean up the endpoint if it contains deployment-specific paths
            if '/openai' in azure_endpoint:
                azure_endpoint = azure_endpoint.split('/openai')[0]
            
            # Remove any trailing slashes
            azure_endpoint = azure_endpoint.rstrip('/')
            
            print(f"Using Azure OpenAI endpoint: {azure_endpoint} with API version: {api_version}")
            
            # Configure Azure OpenAI client with specific timeout and retry settings
            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                timeout=timeout,
                max_retries=3  # Add max retries for better reliability
            )
        else:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=3
            )
        self.active_requests: Dict[str, asyncio.Event] = {}
    
    async def create_chat_completion(self, request: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Send chat completion to OpenAI API with cancellation support."""
        
        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event
        
        try:
            # Create task that can be cancelled
            completion_task = asyncio.create_task(
                self.client.chat.completions.create(**request)
            )
            
            if request_id:
                # Wait for either completion or cancellation
                cancel_task = asyncio.create_task(cancel_event.wait())
                done, pending = await asyncio.wait(
                    [completion_task, cancel_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Check if request was cancelled
                if cancel_task in done:
                    completion_task.cancel()
                    raise HTTPException(status_code=499, detail="Request cancelled by client")
                
                completion = await completion_task
            else:
                completion = await completion_task
            
            # Convert to dict format that matches the original interface
            return completion.model_dump()
        
        except AuthenticationError as e:
            raise HTTPException(status_code=401, detail=self.classify_openai_error(str(e)))
        except RateLimitError as e:
            raise HTTPException(status_code=429, detail=self.classify_openai_error(str(e)))
        except BadRequestError as e:
            raise HTTPException(status_code=400, detail=self.classify_openai_error(str(e)))
        except APIError as e:
            status_code = getattr(e, 'status_code', 500)
            raise HTTPException(status_code=status_code, detail=self.classify_openai_error(str(e)))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
        
        finally:
            # Clean up active request tracking
            if request_id and request_id in self.active_requests:
                del self.active_requests[request_id]
    
    async def create_chat_completion_stream(self, request: Dict[str, Any], request_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Send streaming chat completion to OpenAI API with cancellation support."""
        
        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event
        
        streaming_completion = None
        
        try:
            # Ensure stream is enabled
            request["stream"] = True
            
            # Log the request for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Creating streaming completion with request: {json.dumps({k: v for k, v in request.items() if k != 'messages'}, indent=2)}")
            
            # Create the streaming completion with simpler error handling
            try:
                streaming_completion = await self.client.chat.completions.create(**request)
                logger.debug("Streaming completion created successfully")
            except Exception as e:
                logger.error(f"Failed to create streaming completion: {e}")
                error_data = {
                    "error": {
                        "type": "connection_error",
                        "message": f"Failed to start streaming: {str(e)}"
                    }
                }
                yield f"data: {json.dumps(error_data)}"
                return
            
            # Handle the async iteration with explicit iterator handling for Azure compatibility
            chunk_count = 0
            logger.debug("Starting to iterate over streaming chunks")
            
            # Use explicit async iterator to handle Azure OpenAI streaming properly
            stream_iterator = streaming_completion.__aiter__()
            stream_finished = False
            
            while not stream_finished:
                try:
                    # Get next chunk with timeout
                    chunk = await asyncio.wait_for(stream_iterator.__anext__(), timeout=30.0)
                    chunk_count += 1
                    logger.debug(f"Processing chunk {chunk_count}")
                    
                    # Quick cancellation check
                    if request_id and request_id in self.active_requests and self.active_requests[request_id].is_set():
                        logger.info(f"Request {request_id} cancelled by client")
                        error_data = {
                            "error": {
                                "type": "client_error",
                                "message": "Request cancelled by client"
                            }
                        }
                        yield f"data: {json.dumps(error_data)}"
                        return
                    
                    # Process and yield chunk immediately
                    try:
                        chunk_dict = chunk.model_dump()
                        chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
                        logger.debug(f"Yielding chunk {chunk_count}: {len(chunk_json)} characters")
                        yield f"data: {chunk_json}"
                        
                        # Check if this chunk indicates the end of the stream
                        if chunk_dict.get('choices') and len(chunk_dict['choices']) > 0:
                            choice = chunk_dict['choices'][0]
                            if choice.get('finish_reason') in ['stop', 'length', 'function_call', 'tool_calls', 'content_filter']:
                                logger.debug(f"Stream finished with reason: {choice.get('finish_reason')}")
                                stream_finished = True
                                break
                                
                    except Exception as chunk_error:
                        logger.warning(f"Error processing chunk {chunk_count}: {chunk_error}")
                        continue
                        
                except StopAsyncIteration:
                    logger.debug("Stream ended normally via StopAsyncIteration")
                    stream_finished = True
                    break
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for chunk {chunk_count + 1}")
                    error_data = {
                        "error": {
                            "type": "timeout_error",
                            "message": f"Timeout waiting for streaming chunk after {chunk_count} chunks"
                        }
                    }
                    yield f"data: {json.dumps(error_data)}"
                    return
                except Exception as stream_error:
                    logger.error(f"Error during streaming iteration: {stream_error}")
                    error_data = {
                        "error": {
                            "type": "stream_error",
                            "message": f"Streaming error: {str(stream_error)}"
                        }
                    }
                    yield f"data: {json.dumps(error_data)}"
                    return
            
            logger.debug(f"Streaming completed after {chunk_count} chunks")
            yield "data: [DONE]"
                
        except (AuthenticationError, RateLimitError, BadRequestError, APIError) as e:
            # For streaming responses, we need to yield error data instead of raising HTTPException
            status_code = getattr(e, 'status_code', 500)
            if isinstance(e, AuthenticationError):
                status_code = 401
            elif isinstance(e, RateLimitError):
                status_code = 429
            elif isinstance(e, BadRequestError):
                status_code = 400
            
            error_detail = self.classify_openai_error(str(e))
            error_data = {
                "error": {
                    "type": "api_error",
                    "status_code": status_code,
                    "message": error_detail
                }
            }
            yield f"data: {json.dumps(error_data)}"
            return
            
        except Exception as e:
            # For unexpected errors in streaming, also yield error data
            logger.error(f"Unexpected streaming error: {e}")
            error_data = {
                "error": {
                    "type": "internal_error", 
                    "status_code": 500,
                    "message": f"Unexpected error: {str(e)}"
                }
            }
            yield f"data: {json.dumps(error_data)}"
            return
        
        finally:
            # Clean up active request tracking
            if request_id and request_id in self.active_requests:
                del self.active_requests[request_id]

    async def _handle_azure_streaming_alternative(self, request: Dict[str, Any], request_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Alternative streaming implementation for Azure OpenAI when regular streaming fails."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Use a shorter timeout for Azure streaming
            logger.debug("Trying alternative Azure streaming approach")
            
            # Create the streaming completion with explicit timeout handling
            stream_task = asyncio.create_task(
                self.client.chat.completions.create(**request)
            )
            
            try:
                streaming_completion = await asyncio.wait_for(stream_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("Azure streaming creation timed out")
                stream_task.cancel()
                error_data = {
                    "error": {
                        "type": "timeout_error",
                        "message": "Azure streaming creation timed out"
                    }
                }
                yield f"data: {json.dumps(error_data)}"
                return
            
            chunk_count = 0
            last_chunk_time = asyncio.get_event_loop().time()
            
            # Iterate through chunks with timeout protection
            while True:
                try:
                    # Wait for next chunk with timeout
                    chunk = await asyncio.wait_for(streaming_completion.__anext__(), timeout=30.0)
                    
                    chunk_count += 1
                    current_time = asyncio.get_event_loop().time()
                    logger.debug(f"Received chunk {chunk_count} after {current_time - last_chunk_time:.2f}s")
                    last_chunk_time = current_time
                    
                    # Check for cancellation
                    if request_id and request_id in self.active_requests:
                        if self.active_requests[request_id].is_set():
                            logger.info(f"Request {request_id} cancelled")
                            error_data = {
                                "error": {
                                    "type": "client_error",
                                    "message": "Request cancelled by client"
                                }
                            }
                            yield f"data: {json.dumps(error_data)}"
                            return
                    
                    # Process chunk
                    try:
                        chunk_dict = chunk.model_dump()
                        chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
                        yield f"data: {chunk_json}"
                    except Exception as chunk_error:
                        logger.warning(f"Error processing chunk {chunk_count}: {chunk_error}")
                        continue
                        
                except StopAsyncIteration:
                    logger.debug(f"Streaming completed normally after {chunk_count} chunks")
                    break
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for chunk after {chunk_count} chunks")
                    error_data = {
                        "error": {
                            "type": "timeout_error",
                            "message": f"Timeout waiting for streaming chunk after {chunk_count} chunks"
                        }
                    }
                    yield f"data: {json.dumps(error_data)}"
                    return
                except Exception as chunk_error:
                    logger.error(f"Error getting chunk {chunk_count + 1}: {chunk_error}")
                    error_data = {
                        "error": {
                            "type": "stream_error",
                            "message": f"Error reading stream: {str(chunk_error)}"
                        }
                    }
                    yield f"data: {json.dumps(error_data)}"
                    return
            
            yield "data: [DONE]"
            
        except Exception as e:
            logger.error(f"Alternative streaming failed: {e}")
            error_data = {
                "error": {
                    "type": "stream_error",
                    "message": f"Alternative streaming failed: {str(e)}"
                }
            }
            yield f"data: {json.dumps(error_data)}"
    
    def classify_openai_error(self, error_detail: Any) -> str:
        """Provide specific error guidance for common OpenAI API issues."""
        error_str = str(error_detail).lower()
        
        # Azure-specific errors
        if "resource not found" in error_str and "404" in error_str:
            return "Azure OpenAI resource not found. Please check your deployment name, endpoint URL, and API version. Ensure the model deployment exists and is properly configured."
        
        # Region/country restrictions
        if "unsupported_country_region_territory" in error_str or "country, region, or territory not supported" in error_str:
            return "OpenAI API is not available in your region. Consider using a VPN or Azure OpenAI service."
        
        # API key issues
        if "invalid_api_key" in error_str or "unauthorized" in error_str:
            return "Invalid API key. Please check your OPENAI_API_KEY configuration."
        
        # Rate limiting
        if "rate_limit" in error_str or "quota" in error_str:
            return "Rate limit exceeded. Please wait and try again, or upgrade your API plan."
        
        # Model not found
        if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
            return "Model not found. Please check your BIG_MODEL and SMALL_MODEL configuration."
        
        # Billing issues
        if "billing" in error_str or "payment" in error_str:
            return "Billing issue. Please check your OpenAI account billing status."
        
        # Azure endpoint issues
        if "azure" in error_str and "endpoint" in error_str:
            return "Azure OpenAI endpoint configuration issue. Please verify your OPENAI_BASE_URL and AZURE_API_VERSION settings."
        
        # Default: return original message
        return str(error_detail)
    
    def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request by request_id."""
        if request_id in self.active_requests:
            self.active_requests[request_id].set()
            return True
        return False