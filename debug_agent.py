#!/usr/bin/env python3

import asyncio
import json
from src.core.agent import AgentManager, AgentError
from src.config.settings import Settings
from dotenv import load_dotenv

async def main():
    print("Debug Agent Interface")
    print("Type 'exit' to quit")
    print("-" * 50)
    
    while True:
        try:
            # Reload environment variables before each request
            load_dotenv(override=True)
            
            # Reinitialize settings and agent manager with fresh env variables
            settings = Settings()
            agent_config = settings.get_agent_config()
            agent_manager = AgentManager(**agent_config)
            
            # Show current settings
            print(f"\nCurrent settings:")
            print(f"Model: {agent_config['model']}")
            print(f"Temperature: {agent_config['temperature']}")
            print(f"Max tokens: {agent_config['max_tokens']}")
            print(f"MCP URL: {agent_config['mcp_proxy_url']}")
            print("-" * 50)
            
            # Get user input
            user_input = input("\nEnter your question: ")
            
            if user_input.lower() == 'exit':
                break
            
            # Process the message
            print("\nProcessing your request...")
            response = await agent_manager.process_message_robust(
                message=user_input,
                streaming=False  # Disable streaming for cleaner debug output
            )
            
            print("\nResponse:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            
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