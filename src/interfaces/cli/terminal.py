#!/usr/bin/env python3

import asyncio
import argparse
from typing import Optional

from src.core.agent import AgentManager
from src.config.settings import Settings

class TerminalInterface:
    """
    Terminal interface for interacting with the agent.
    Handles command-line arguments and user interaction in the terminal.
    """
    
    def __init__(self):
        """Initialize the terminal interface."""
        self.settings = Settings()
        self.agent_config = self.settings.get_agent_config()
        
    async def _show_loading(self):
        """Display a loading animation while waiting for a response."""
        chars = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
        i = 0
        while True:
            print(f"\r{chars[i % len(chars)]}", end="", flush=True)
            i += 1
            await asyncio.sleep(0.1)
    
    def parse_arguments(self):
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(description="OpenAI Agent with MCP Server")
        parser.add_argument("--no-stream", action="store_true", help="Use non-streaming mode")
        parser.add_argument("--model", type=str, default=self.settings.default_model,
                        help=f"OpenAI model to use (default: {self.settings.default_model})")
        parser.add_argument("--temperature", type=float, default=self.settings.temperature,
                        help=f"Model temperature (default: {self.settings.temperature})")
        parser.add_argument("--max-tokens", type=int, default=self.settings.max_tokens,
                        help=f"Maximum tokens (default: {self.settings.max_tokens})")
        return parser.parse_args()
    
    async def run(self):
        """Run the terminal interface."""
        args = self.parse_arguments()
        
        # Update config with command line arguments
        self.agent_config["model"] = args.model
        self.agent_config["temperature"] = args.temperature
        self.agent_config["max_tokens"] = args.max_tokens
        
        streaming_mode = not args.no_stream
        
        # Create agent manager
        agent_manager = AgentManager(**self.agent_config)
        
        # Print welcome message
        print("OpenAI Agent with MCP Server")
        print(f"Mode: {'Streaming' if streaming_mode else 'Non-streaming'}")
        print(f"Model: {args.model}")
        print(f"Temperature: {args.temperature}")
        print(f"Max Tokens: {args.max_tokens}")
        print("Type 'exit' to quit\n")
        
        while True:
            try:
                prompt = input("👤 You: ")
                if prompt.lower() in ("exit", "quit"):
                    break
                
                print("🤖 Assistant: ", end="", flush=True)
                
                if streaming_mode:
                    # Run agent with streaming
                    async for chunk in await agent_manager.process_message(
                        message=prompt, 
                        streaming=True
                    ):
                        print(chunk, end="", flush=True)
                    print()  # Newline after response
                else:
                    # Show a loading indicator
                    loading_task = asyncio.create_task(self._show_loading())
                    
                    # Run agent without streaming
                    response = await agent_manager.process_message(
                        message=prompt,
                        streaming=False
                    )
                    
                    # Cancel the loading indicator
                    loading_task.cancel()
                    try:
                        await loading_task
                    except asyncio.CancelledError:
                        pass
                    
                    # Clear the loading indicator and print the response
                    print("\r" + " " * 10 + "\r" + response)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
                
def main():
    """Entry point for the terminal interface."""
    terminal = TerminalInterface()
    asyncio.run(terminal.run())

if __name__ == "__main__":
    main() 