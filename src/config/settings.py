#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional


class Settings:
    """
    Configuration settings manager for the application.
    Loads settings from environment variables and provides accessor methods.
    
    This is implemented as a singleton to ensure environment variables
    are loaded only once and consistently accessed throughout the application.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, env_file: Optional[str] = None, force_reload: bool = False):
        """
        Create a singleton instance of Settings.
        
        Args:
            env_file: Optional path to a .env file to load
            force_reload: Whether to force reload environment variables
        """
        if cls._instance is None or force_reload:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._initialized = False
        return cls._instance
    
    def __init__(self, env_file: Optional[str] = None, force_reload: bool = False):
        """
        Initialize settings by loading from environment variables.
        
        Args:
            env_file: Optional path to a .env file to load
            force_reload: Whether to force reload environment variables
        """
        # Skip initialization if already initialized and not forcing reload
        if self._initialized and not force_reload:
            return
            
        # Find the .env file if not specified
        if env_file is None:
            env_path = Path(__file__).resolve().parent.parent.parent / '.env'
            load_dotenv(env_path, override=force_reload)
        else:
            load_dotenv(env_file, override=force_reload)
            
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
        
        # Agent settings
        self.default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4.1-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "500000"))
        
        # MCP Proxy settings
        self.mcp_proxy_command = os.getenv("MCP_PROXY_COMMAND", "/Users/frankhe/.local/bin/mcp-proxy")
        self.mcp_proxy_url = os.getenv("MCP_PROXY_URL", "https://sequencer-v2.heurist.xyz/toole54a5b50/sse")
        
        # Telegram Bot settings
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = self._parse_chat_id()
        
        # Mark as initialized
        self._initialized = True
    
    @classmethod
    def reload(cls):
        """Force reload all environment variables."""
        return cls(force_reload=True)
    
    def _parse_chat_id(self) -> Optional[int]:
        """Parse the Telegram chat ID from environment variables."""
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not chat_id:
            return None
        try:
            return int(chat_id)
        except ValueError:
            raise ValueError("TELEGRAM_CHAT_ID must be a valid integer")
    
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
        return bool(self.telegram_token and self.telegram_chat_id) 