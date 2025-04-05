#!/usr/bin/env python3

import os
import asyncio
import json
import time
import random
from typing import AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerStdio

class AgentError(Exception):
    """Custom error class for agent-related errors"""
    def __init__(self, message: str, details: Optional[Dict] = None, retriable: bool = False):
        super().__init__(message)
        self.details = details
        self.retriable = retriable

class AgentManager:
    """
    Core Agent Manager class that handles agent interactions.
    This class encapsulates all the OpenAI Agent SDK functionality.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 10000,
        mcp_proxy_command: str = "/Users/frankhe/.local/bin/mcp-proxy",
        mcp_proxy_url: str = "https://sequencer-v2.heurist.xyz/toolf22e9e8c/sse",
        instructions: str = "You are a helpful assistant that uses tools to answer user questions use your available tools to answer the user's question the best you can with all your full efforts. You must use the language of the user's question to respond to the user's question.",
        max_retries: int = 3,
        retry_delay_base: float = 1.0
    ):
        """
        Initialize the Agent Manager.
        
        Args:
            model: The OpenAI model to use
            temperature: Model temperature setting
            max_tokens: Maximum tokens for response
            mcp_proxy_command: Path to the MCP proxy command
            mcp_proxy_url: URL for the MCP proxy
            instructions: Agent instructions/system prompt
            max_retries: Maximum number of retries for API calls
            retry_delay_base: Base delay (in seconds) for exponential backoff
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_proxy_command = mcp_proxy_command
        self.mcp_proxy_url = mcp_proxy_url
        self.instructions = instructions
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.client = OpenAI()
        self.fallback_models = ["gpt-4o-mini"]

    async def _exponential_backoff(self, retry_count: int) -> None:
        """Exponential backoff with jitter for retries."""
        delay = self.retry_delay_base * (2 ** retry_count) + random.uniform(0, 1)
        await asyncio.sleep(delay)

    async def _create_agent_with_retry(self):
        """Create and return an OpenAI agent instance with retries."""
        last_exception = None
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        
        for retry in range(self.max_retries):
            for model_idx, current_model in enumerate(models_to_try):
                try:
                    # Generate trace ID for this run
                    self.trace_id = gen_trace_id()
                    
                    # Create MCP server
                    self.mcp_server = MCPServerStdio(
                        name="MCP Proxy Server",
                        params={
                            "command": self.mcp_proxy_command,
                            "args": [self.mcp_proxy_url],
                        }
                    )
                    
                    # Create the agent with model settings
                    model_settings = ModelSettings(
                        temperature=self.temperature,
                        max_tokens=min(self.max_tokens, 4000),  # Cap max_tokens to prevent errors
                    )
                    
                    agent = OpenAIAgent(
                        name="Assistant",
                        instructions=self.instructions,
                        mcp_servers=[self.mcp_server],
                        model=current_model,
                        model_settings=model_settings
                    )
                    
                    # If using a fallback model, log it
                    if current_model != self.model:
                        print(f"Using fallback model: {current_model} instead of {self.model}")
                    
                    return agent
                except Exception as e:
                    last_exception = e
                    error_details = {
                        "type": type(e).__name__,
                        "message": str(e),
                        "model": current_model,
                        "mcp_proxy_command": self.mcp_proxy_command,
                        "retry": retry,
                        "model_attempt": model_idx + 1
                    }
                    
                    # If we've tried all models in this retry, wait before the next retry
                    if model_idx == len(models_to_try) - 1 and retry < self.max_retries - 1:
                        await self._exponential_backoff(retry)
                    
                    # Continue to the next model or retry
        
        # If we get here, all retries and model attempts failed
        raise AgentError("Failed to create agent after multiple retries", error_details, retriable=False)

    async def _run_agent_with_retry(self, agent, message):
        """Run the agent with retry logic."""
        last_exception = None
        
        for retry in range(self.max_retries):
            try:
                result = await Runner.run(
                    starting_agent=agent,
                    input=message
                )
                return result
            except OpenAIError as e:
                last_exception = e
                error_details = {
                    "type": "OpenAIError",
                    "message": str(e),
                    "request_id": getattr(e, 'request_id', None),
                    "status_code": getattr(e, 'status_code', None),
                    "retry": retry + 1,
                    "max_retries": self.max_retries
                }
                
                # Check if error is retriable (500 server errors typically are)
                retriable = getattr(e, 'status_code', 0) >= 500 or "server_error" in str(e).lower()
                
                if not retriable or retry >= self.max_retries - 1:
                    raise AgentError("OpenAI API error occurred", error_details, retriable=retriable) from e
                
                # Log retry attempt
                print(f"Retrying after OpenAI API error (attempt {retry+1}/{self.max_retries}): {str(e)}")
                await self._exponential_backoff(retry)
            except Exception as e:
                last_exception = e
                error_details = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "retry": retry + 1,
                    "max_retries": self.max_retries
                }
                
                # For non-OpenAI errors, only retry a limited number of times
                if retry >= self.max_retries - 1:
                    raise AgentError("Error running agent", error_details, retriable=False) from e
                
                # Log retry attempt
                print(f"Retrying after error (attempt {retry+1}/{self.max_retries}): {str(e)}")
                await self._exponential_backoff(retry)
        
        # We should never reach here, but just in case
        raise AgentError("Failed to run agent after maximum retries", {
            "type": type(last_exception).__name__ if last_exception else "Unknown",
            "message": str(last_exception) if last_exception else "Unknown error"
        }, retriable=False)

    async def process_message(
        self, 
        message: str,
        streaming: bool = True
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Process a user message and return response.
        
        Args:
            message: The user message to process
            streaming: Whether to return a streaming response
        
        Returns:
            Either a complete response string or an async generator for streaming
        """
        try:
            # Create agent first to initialize mcp_server with retries
            agent = await self._create_agent_with_retry()
            
            # Now we can use self.mcp_server which was created in _create_agent
            async with self.mcp_server:
                # Run with tracing
                with trace(workflow_name="MCP Agent", trace_id=self.trace_id):
                    trace_url = f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
                    
                    # Run the agent with retries
                    result = await self._run_agent_with_retry(agent, message)
                    
                    if streaming:
                        # For streaming, split the response into chunks
                        async def stream_response():
                            yield f"View trace: {trace_url}\n\n"
                            for chunk in result.final_output.split():
                                yield chunk + " "
                        return stream_response()
                    else:
                        return f"View trace: {trace_url}\n\n{result.final_output}"
        except AgentError as e:
            # If error is retriable and we have capacity to retry at a higher level
            if e.retriable and hasattr(self, '_top_level_retry_count') and self._top_level_retry_count < 2:
                self._top_level_retry_count += 1
                print(f"Top-level retry {self._top_level_retry_count}/2 after error: {str(e)}")
                await asyncio.sleep(2 * self._top_level_retry_count)  # Wait before retry
                return await self.process_message(message, streaming)
            raise e
        except Exception as e:
            if isinstance(e, AgentError):
                raise e
            error_details = {
                "type": type(e).__name__,
                "message": str(e)
            }
            raise AgentError("Unexpected error occurred", error_details, retriable=False) from e

    async def process_message_robust(
        self,
        message: str,
        streaming: bool = True
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Process a message with top-level retries for extra robustness.
        """
        # Initialize top-level retry counter
        self._top_level_retry_count = 0
        
        # Try with different URL patterns if we encounter persistent errors
        original_url = self.mcp_proxy_url
        url_patterns = [
            original_url,
            "https://sequencer-v2.heurist.xyz/mcp/sse",  # Generic endpoint
            "https://sequencer.openai.com/mcp/sse",      # Alternative endpoint
        ]
        
        last_exception = None
        for url_idx, url in enumerate(url_patterns):
            try:
                # Set the current URL to try
                self.mcp_proxy_url = url
                return await self.process_message(message, streaming)
            except AgentError as e:
                last_exception = e
                # Only continue if we have more URLs to try
                if url_idx < len(url_patterns) - 1:
                    print(f"Trying alternative MCP URL after error: {e}")
                    await asyncio.sleep(1)  # Small delay before trying next URL
                else:
                    # Restore original URL before raising
                    self.mcp_proxy_url = original_url
                    raise e
            except Exception as e:
                last_exception = e
                # Restore original URL before raising
                self.mcp_proxy_url = original_url
                error_details = {
                    "type": type(e).__name__,
                    "message": str(e)
                }
                raise AgentError("Unexpected error in robust processing", error_details, retriable=False) from e
        
        # Restore original URL before raising
        self.mcp_proxy_url = original_url
        raise last_exception or AgentError("Failed to process message with all URL patterns", {}, retriable=False)

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}" 