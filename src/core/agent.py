#!/usr/bin/env python3

import os
import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

from openai import OpenAI
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerStdio

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
        mcp_proxy_url: str = "https://sequencer-v2.heurist.xyz/mcp/sse",
        instructions: str = "You are a helpful assistant that uses tools to answer user questions."
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
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_proxy_command = mcp_proxy_command
        self.mcp_proxy_url = mcp_proxy_url
        self.instructions = instructions
        self.client = OpenAI()

    async def _create_agent(self):
        """Create and return an OpenAI agent instance with MCP server."""
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
            max_tokens=self.max_tokens,
        )
        
        agent = OpenAIAgent(
            name="Assistant",
            instructions=self.instructions,
            mcp_servers=[self.mcp_server],
            model=self.model,
            model_settings=model_settings
        )
        
        return agent

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
        async with self.mcp_server:
            agent = await self._create_agent()
            
            # Run with tracing
            with trace(workflow_name="MCP Agent", trace_id=self.trace_id):
                trace_url = f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
                
                # Run the agent
                result = await Runner.run(
                    starting_agent=agent,
                    input=message
                )
                
                if streaming:
                    # For streaming, split the response into chunks
                    async def stream_response():
                        yield f"View trace: {trace_url}\n\n"
                        for chunk in result.final_output.split():
                            yield chunk + " "
                    return stream_response()
                else:
                    return f"View trace: {trace_url}\n\n{result.final_output}"

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}" 