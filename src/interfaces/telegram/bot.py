#!/usr/bin/env python3

import asyncio
import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.core.agent import AgentManager
from src.config.settings import Settings

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramInterface:
    """
    Telegram interface for interacting with the agent.
    Handles Telegram bot commands and user messages.
    """
    
    def __init__(self):
        """Initialize the Telegram interface."""
        self.settings = Settings()
        self.agent_config = self.settings.get_agent_config()
        
        if not self.settings.is_telegram_configured():
            raise ValueError("Telegram bot token not found. Set TELEGRAM_BOT_TOKEN in .env file.")
        
        self.token = self.settings.telegram_token
        self.allowed_users = self.settings.telegram_allowed_users
        
        # Create agent manager
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Store active users and their conversations
        self.active_users: Dict[int, Dict[str, Any]] = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        user = update.effective_user
        user_id = user.id
        
        # Check if user is allowed
        if self.allowed_users and user_id not in self.allowed_users:
            await update.message.reply_text(
                "Sorry, you are not authorized to use this bot."
            )
            return
            
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": user.full_name,
                "username": user.username,
                "history": []
            }
        
        await update.message.reply_text(
            f"Hello {user.full_name}! I'm an AI assistant powered by OpenAI.\n"
            f"I'm here to help you with your questions. Just send me a message!"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command."""
        user_id = update.effective_user.id
        
        # Check if user is allowed
        if self.allowed_users and user_id not in self.allowed_users:
            return
            
        await update.message.reply_text(
            "Here are the available commands:\n"
            "/start - Start the conversation\n"
            "/help - Show this help message\n"
            "/model - Show the current AI model\n"
            "/stats - Show your usage statistics\n\n"
            "Simply send me a message, and I'll respond with the help of various tools!"
        )
    
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /model command."""
        user_id = update.effective_user.id
        
        # Check if user is allowed
        if self.allowed_users and user_id not in self.allowed_users:
            return
            
        await update.message.reply_text(
            f"Current model: {self.agent_config['model']}\n"
            f"Temperature: {self.agent_config['temperature']}\n"
            f"Max tokens: {self.agent_config['max_tokens']}"
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /stats command."""
        user_id = update.effective_user.id
        
        # Check if user is allowed
        if self.allowed_users and user_id not in self.allowed_users:
            return
            
        if user_id in self.active_users:
            user_data = self.active_users[user_id]
            message_count = len(user_data["history"])
            await update.message.reply_text(
                f"Your statistics:\n"
                f"Messages sent: {message_count}"
            )
        else:
            await update.message.reply_text(
                "No statistics available. Start a conversation first."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages."""
        user_id = update.effective_user.id
        
        # Check if user is allowed
        if self.allowed_users and user_id not in self.allowed_users:
            await update.message.reply_text(
                "Sorry, you are not authorized to use this bot."
            )
            return
            
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": update.effective_user.full_name,
                "username": update.effective_user.username,
                "history": []
            }
        
        message_text = update.message.text
        self.active_users[user_id]["history"].append({"role": "user", "content": message_text})
        
        # Send "typing" action
        await update.message.chat.send_action(action="typing")
        
        try:
            # Process message through agent
            waiting_message = await update.message.reply_text("Processing your request...")
            
            response = await self.agent_manager.process_message(
                message=message_text,
                streaming=False  # Telegram doesn't support streaming well
            )
            
            # Store response in history
            self.active_users[user_id]["history"].append({"role": "assistant", "content": response})
            
            # Extract trace URL from response
            trace_url = None
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                trace_url = parts[0].replace("View trace: ", "")
                response = parts[1] if len(parts) > 1 else ""
            
            # Send response
            await waiting_message.delete()
            await update.message.reply_text(response)
            
            # Send trace URL separately if available
            if trace_url:
                await update.message.reply_text(
                    f"[View interaction trace]({trace_url})",
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                f"Sorry, there was an error processing your request: {str(e)}"
            )
    
    async def run(self) -> None:
        """Run the Telegram bot."""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("model", self.model_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        logger.info("Starting Telegram bot")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Entry point for the Telegram interface."""
    try:
        telegram_interface = TelegramInterface()
        asyncio.run(telegram_interface.run())
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 