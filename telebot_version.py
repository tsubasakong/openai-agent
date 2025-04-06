#!/usr/bin/env python3

"""
Adapter script to maintain backward compatibility with telebot_version.py.
Now it simply imports and runs the modular version from the new interface structure.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Entry point for the Telegram interface."""
    # Import from the new interface structure
    from src.interfaces.telegram.bot import main as telegram_main
    
    # Log that we're using the adapter
    logger.info("Running Telegram bot via compatibility adapter (telebot_version.py)")
    
    # Run the modular version
    telegram_main()

if __name__ == "__main__":
    main() 