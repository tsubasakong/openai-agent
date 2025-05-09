#!/usr/bin/env python3

import os
import asyncio
import json
import time
import random
from typing import AsyncGenerator, Dict, List, Optional, Union, Callable, Any
from pathlib import Path
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents import InputGuardrail, GuardrailFunctionOutput
from agents.mcp import MCPServerStdio
from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    ModelBehaviorError,
    UserError,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered
)
from pydantic import BaseModel


# Default instructions for the Solana meme coin analyst agent
DEFAULT_INSTRUCTIONS = """You are a specialized Solana meme coin analyst who integrates both on-chain data and social signals. You will analyze the following aspects of Solana meme coins:

1. Token Background: Research the token's origins, its narratives, and founding team using web search and dexscreener search. If the token address is provided, use it as a search query. The token address format example in solana is 83astqz8y8w8q174vfanrky3wejk9245pd82h7q224wq9k3q9234 or has "pump" at its end, for address on evm, it starts with 0x. Use your best effort to figure out the exact whole token address at first. Look for information about when it was launched, who created it, and its intended purpose or community.

2. On-Chain Analysis: Examine blockchain data including holder metrics, liquidity pools, trading volume, wallet distribution, and notable transactions. For accurate liquidity pool info, use dexscreener as the first source.

3. (Optional) When wallet address is provided, you should use it as a search query to get the wallet's transaction history and balance.

4. Social Signals: Evaluate Twitter engagement, sentiment analysis, influencer coverage, and community growth. If you mentioned a tweet, you should provide the tweet url. If you mentioned a user, you should provide the user's profile url.

5. Key People Analysis: When any Twitter handles, usernames, or individuals are mentioned in relation to the token, research their background, credibility, past projects, and specific relationship to this token. Search with handle @username with higher priority, then search with username username, then search with name full name.

6. GMGN Links: Whenever you mention or identify a token address on Solana, include a GMGN link in this format: https://gmgn.ai/sol/token/{token_address}. Whenever you mention or identify a Solana wallet address, include a GMGN link in this format: https://gmgn.ai/sol/address/{wallet_address}. Always include these links immediately after mentioning the address. MUST REMEMBER: DO NOT include the GMGN link in the output if the token address is not on sol chain. 

For Heurist AI token, the coingecko id is heurist. the token address on base chain is 0x7c42dd1556754be827e187ce0870e70c5e571f35. When using dexscreener, the search term is heurist.
Organize your response with clear sections for token background, on-chain metrics, wallet analysis, social signals, and key people analysis. Prioritize objective data over hype and identify both bullish and bearish signals. Support your analysis with specific, current data points whenever possible.

Use the user's query language to write your response. For example, if user's query is in Chinese, write your response in Chinese. If user's query is in English, write your response in English.
"""

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
        model: str = "gpt-4.1-mini",
        temperature: float = 0.1,
        max_tokens: int = 1000000,
        mcp_proxy_command: str = "/Users/frankhe/.local/bin/mcp-proxy",
        mcp_proxy_url: str = "https://sequencer-v2.heurist.xyz/toolc1530ff5/sse",
        instructions: str = DEFAULT_INSTRUCTIONS,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
        handoffs: List[OpenAIAgent] = None,
        input_guardrails: List[InputGuardrail] = None,
        context: Optional[Dict[str, Any]] = None,
        enable_mcp_cache: bool = True,
        cache_ttl_seconds: int = 3600,  # Default: 1 hour cache lifetime
        enable_guardrails: bool = True  # New option to enable/disable guardrails
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
            handoffs: List of agents that this agent can hand off to
            input_guardrails: List of input guardrails to apply
            context: Initial context for the agent
            enable_mcp_cache: Whether to enable caching for MCP server responses
            cache_ttl_seconds: Time-to-live for cached MCP responses in seconds
            enable_guardrails: Whether to enable guardrail functionality
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
        self.handoffs = handoffs or []
        self.input_guardrails = input_guardrails or []
        self.context = context or {}
        self.enable_mcp_cache = enable_mcp_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_guardrails = enable_guardrails
        
        self.fallback_models = ["gpt-4o-mini"]
        self.mcp_server = None

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
                    
                    # Create MCP server with proper tool caching
                    self.mcp_server = MCPServerStdio(
                        name="MCP Proxy Server",
                        params={
                            "command": self.mcp_proxy_command,
                            "args": [self.mcp_proxy_url],
                        },
                        # Enable tools caching per the OpenAI SDK documentation
                        cache_tools_list=self.enable_mcp_cache
                    )
                    
                    # Create the agent with model settings
                    model_settings = ModelSettings(
                        temperature=self.temperature,
                        max_tokens=min(self.max_tokens, 10000),  # Cap max_tokens to prevent errors
                    )
                    
                    # Apply guardrails only if enabled
                    active_guardrails = self.input_guardrails if self.enable_guardrails else []
                    
                    agent = OpenAIAgent(
                        name="Assistant",
                        instructions=self.instructions,
                        mcp_servers=[self.mcp_server],
                        model=current_model,
                        model_settings=model_settings,
                        handoffs=self.handoffs,
                        input_guardrails=active_guardrails
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
                    input=message,
                    context=self.context
                )
                
                # Update context with any new values from the result
                if hasattr(result, 'context') and result.context:
                    self.context.update(result.context)
                
                return result
            except MaxTurnsExceeded as e:
                # Maximum back-and-forth exceeded
                error_details = {
                    "type": "MaxTurnsExceeded", 
                    "message": e.message,
                    "retry": retry + 1,
                    "max_retries": self.max_retries
                }
                
                print(f"Max turns exceeded error: {e.message}")
                if retry >= self.max_retries - 1:
                    raise AgentError(
                        f"Conversation exceeded maximum turns: {e.message}",
                        error_details,
                        retriable=False
                    ) from e
                
                # Try again with a different retry
                await self._exponential_backoff(retry)
                
            except ModelBehaviorError as e:
                # Model calling nonexistent tools or providing malformed JSON
                error_details = {
                    "type": "ModelBehaviorError", 
                    "message": e.message,
                    "retry": retry + 1,
                    "max_retries": self.max_retries
                }
                
                print(f"Model behavior error: {e.message}")
                # This could be due to complex query with too many tool calls
                # Try again with a different retry
                if retry >= self.max_retries - 1:
                    raise AgentError(
                        f"Model behavior error: {e.message}",
                        error_details,
                        retriable=True  # May be worth retrying with a different prompt
                    ) from e
                
                await self._exponential_backoff(retry)
                
            except InputGuardrailTripwireTriggered as e:
                # Input guardrail was triggered
                error_details = {
                    "type": "InputGuardrailTriggered", 
                    "guardrail": e.guardrail_result.guardrail.__class__.__name__,
                    "details": str(e.guardrail_result)
                }
                
                # This is expected behavior for unsafe content, not retriable
                raise AgentError(
                    f"Input guardrail triggered: {e.guardrail_result.guardrail.__class__.__name__}",
                    error_details,
                    retriable=False
                ) from e
                
            except OutputGuardrailTripwireTriggered as e:
                # Output guardrail was triggered
                error_details = {
                    "type": "OutputGuardrailTriggered", 
                    "guardrail": e.guardrail_result.guardrail.__class__.__name__,
                    "details": str(e.guardrail_result)
                }
                
                # This is expected behavior for unsafe content, not retriable
                raise AgentError(
                    f"Output guardrail triggered: {e.guardrail_result.guardrail.__class__.__name__}",
                    error_details,
                    retriable=False
                ) from e
                
            except UserError as e:
                # User error in SDK usage
                error_details = {
                    "type": "UserError", 
                    "message": e.message
                }
                
                # Configuration error, not retriable
                raise AgentError(
                    f"User error in SDK usage: {e.message}",
                    error_details,
                    retriable=False
                ) from e
                
            except AgentsException as e:
                # Generic SDK exception
                error_details = {
                    "type": "AgentsException", 
                    "message": str(e),
                    "retry": retry + 1,
                    "max_retries": self.max_retries
                }
                
                print(f"Generic Agents SDK error: {str(e)}")
                if retry >= self.max_retries - 1:
                    raise AgentError(
                        f"Agents SDK error: {str(e)}",
                        error_details,
                        retriable=(retry < self.max_retries - 1)
                    ) from e
                
                await self._exponential_backoff(retry)
            
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
                    # For 500 server errors related to large outputs, suggest splitting the query
                    if getattr(e, 'status_code', 0) == 500 and "server_error" in str(e).lower():
                        error_details["suggestion"] = "The server error might be due to processing too much data. Try splitting your query into multiple smaller queries or reducing the complexity."
                    
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
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Process a user message and return response.
        
        Args:
            message: The user message to process
            streaming: Whether to return a streaming response
            context_update: Optional dictionary to update the context
        
        Returns:
            Either a complete response string or an async generator for streaming
        """
        try:
            # Update context if provided
            if context_update:
                self.context.update(context_update)
                
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
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
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
            "https://sequencer-v2.heurist.xyz/tool6c4acdfe/sse",  # Generic endpoint
            "https://sequencer-v2.heurist.xyz/tool2782c748/sse",  # Alternative endpoint
        ]
        
        last_exception = None
        for url_idx, url in enumerate(url_patterns):
            try:
                # Set the current URL to try
                self.mcp_proxy_url = url
                return await self.process_message(message, streaming, context_update)
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
    
    def create_guardrail(self, guardrail_function: Callable) -> InputGuardrail:
        """
        Create an input guardrail from a function.
        
        Args:
            guardrail_function: Function that implements the guardrail logic
            
        Returns:
            An InputGuardrail instance
        """
        return InputGuardrail(guardrail_function=guardrail_function)
        
    def add_handoff(self, agent: OpenAIAgent) -> None:
        """
        Add a handoff agent to this agent's handoffs.
        
        Args:
            agent: The agent to add as a handoff option
        """
        if agent not in self.handoffs:
            self.handoffs.append(agent)
    
    def add_guardrail(self, guardrail: InputGuardrail) -> None:
        """
        Add an input guardrail to this agent.
        
        Args:
            guardrail: The guardrail to add
        """
        if guardrail not in self.input_guardrails:
            self.input_guardrails.append(guardrail)
    
    def enable_guardrails(self) -> None:
        """Enable the guardrails functionality."""
        self.enable_guardrails = True
        print("Guardrails enabled.")
        
    def disable_guardrails(self) -> None:
        """Disable the guardrails functionality without removing configured guardrails."""
        self.enable_guardrails = False
        print("Guardrails disabled. They will not be applied during processing.")
            
    def clear_cache(self) -> None:
        """
        Clear the MCP server cache.
        This is useful when you want to force fresh data retrieval.
        """
        if hasattr(self, 'mcp_server') and self.enable_mcp_cache:
            if hasattr(self.mcp_server, 'invalidate_tools_cache'):
                # Use the correct method as per documentation
                self.mcp_server.invalidate_tools_cache()
                print("MCP server tools cache invalidated.")
            else:
                # Fallback for older versions or if the method isn't available
                print("Cache invalidation not directly supported. Recreating MCP server...")
                self.mcp_server = None
                print("MCP server reset. Cache will be rebuilt on next request.") 