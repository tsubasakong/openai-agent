#!/usr/bin/env python3

"""
Debug script for testing the agent directly from the command line.
This is a wrapper around the CLI interface with more detailed error output.
"""

import asyncio
import logging
from dotenv import load_dotenv
from src.interfaces.cli.terminal import TerminalInterface
from src.core.agent import AgentError

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Main debug function."""
    # Load env variables
    load_dotenv(override=True)
    
    terminal = TerminalInterface(streaming=False)
    
    print("Debug Agent Interface")
    print("Type 'exit' to quit")
    print("-" * 50)
    
    while True:
        try:
            # Get user input
            user_input = input("\nEnter your question: ")
            
            if user_input.lower() == 'exit':
                break
            
            # Process with more detailed error output
            await terminal._get_nonstreaming_response(user_input)
            
        except AgentError as e:
            print("\nError occurred!")
            print("-" * 50)
            
            if e.details:
                if e.details.get('type') == 'OpenAIError':
                    print("OpenAI API Error:")
                    print(f"Message: {e.details.get('message')}")
                    print(f"Request ID: {e.details.get('request_id')}")
                    print(f"Status Code: {e.details.get('status_code')}")
                    print(f"Retriable: {e.retriable}")
                else:
                    print(f"Error Type: {e.details.get('type')}")
                    print(f"Message: {e.details.get('message')}")
                    if 'model' in e.details:
                        print(f"Model: {e.details.get('model')}")
                    if 'mcp_proxy_command' in e.details:
                        print(f"MCP Proxy: {e.details.get('mcp_proxy_command')}")
                    print(f"Retriable: {e.retriable}")
            else:
                print(f"Error: {str(e)}")
                print(f"Retriable: {e.retriable}")
            
            print("\nTroubleshooting tips:")
            print("1. Check if your OpenAI API key is valid")
            print("2. Verify the model name is correct")
            print("3. Check if MCP proxy is running")
            print("4. Try rephrasing your question")
            print("5. Edit the .env file to update settings")
            print("-" * 50)
            
        except Exception as e:
            print(f"\nUnexpected error: {type(e).__name__}")
            print(f"Message: {str(e)}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main()) 