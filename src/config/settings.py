#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional

class Settings:
    """
    Configuration settings manager for the application.
    Loads settings from environment variables and provides accessor methods.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize settings by loading from environment variables.
        
        Args:
            env_file: Optional path to a .env file to load
        """
        # Find the .env file if not specified
        if env_file is None:
            env_path = Path(__file__).resolve().parent.parent.parent / '.env'
            load_dotenv(env_path)
        else:
            load_dotenv(env_file)
            
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
        
        # Agent settings
        self.default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
        
        # MCP Proxy settings
        self.mcp_proxy_command = os.getenv("MCP_PROXY_COMMAND", "/Users/frankhe/.local/bin/mcp-proxy")
        self.mcp_proxy_url = os.getenv("MCP_PROXY_URL", "https://sequencer-v2.heurist.xyz/mcp/sse")
        
        # Telegram Bot settings
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_allowed_users = self._parse_allowed_users()
    
    def _parse_allowed_users(self) -> list:
        """Parse the comma-separated list of allowed Telegram user IDs."""
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if not allowed_users_str:
            return []
        
        return [int(user_id.strip()) for user_id in allowed_users_str.split(",") if user_id.strip()]
    
    def get_agent_config(self) -> Dict[str, Any]:
        """Get the agent configuration settings."""
        return {
            "model": self.default_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "mcp_proxy_command": self.mcp_proxy_command,
            "mcp_proxy_url": self.mcp_proxy_url,
        }
    
    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.telegram_token) 