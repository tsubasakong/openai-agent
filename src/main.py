#!/usr/bin/env python3

import os
import sys
import argparse
import asyncio

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="OpenAI Agent with MCP Server")
    parser.add_argument("--telegram", action="store_true", help="Run Telegram bot interface")
    parser.add_argument("--no-stream", action="store_true", help="Use non-streaming mode for CLI")
    parser.add_argument("--model", type=str, help="OpenAI model to use")
    parser.add_argument("--temperature", type=float, help="Model temperature")
    parser.add_argument("--max-tokens", type=int, help="Maximum tokens")
    args = parser.parse_args()
    
    if args.telegram:
        # Run Telegram interface
        from src.interfaces.telegram.bot import main as telegram_main
        telegram_main()
    else:
        # Run CLI interface with optional args
        from src.interfaces.cli.terminal import main as cli_main
        cli_main()

if __name__ == "__main__":
    main() 