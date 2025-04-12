#!/usr/bin/env python3

import os
import logging
import telebot
from dotenv import load_dotenv
from src.core.agent import AgentManager
from src.config.settings import Settings

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBotHandler:
    def __init__(self):
        self.settings = Settings()
        self.agent_config = self.settings.get_agent_config()
        
        if not self.settings.is_telegram_configured():
            raise ValueError("Telegram bot token or chat ID not found. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")
        
        self.token = self.settings.telegram_token
        self.chat_id = self.settings.telegram_chat_id
        
        # Create agent manager
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Store active users and their conversations
        self.active_users = {}
        
        # Initialize the telebot
        self.bot = telebot.TeleBot(self.token)
        self.register_handlers()
        
        # Set up commands
        self.setup_commands()
    
    def setup_commands(self):
        """Set up bot commands that will show up in the Telegram UI"""
        commands = [
            telebot.types.BotCommand("start", "Start the conversation"),
            telebot.types.BotCommand("help", "Show help message"),
            telebot.types.BotCommand("model", "Show current AI model settings"),
            telebot.types.BotCommand("stats", "Show your usage statistics"),
            telebot.types.BotCommand("ask", "Ask me a question"),
            telebot.types.BotCommand("listen", "Start listening to all messages in the chat")
        ]
        self.bot.set_my_commands(commands)
    
    def is_authorized_chat(self, message):
        """Check if the message is from the authorized chat"""
        return message.chat.id == self.chat_id
    
    def extract_entities(self, message):
        """Extract entities (like hyperlinks) from a message and format them for better processing"""
        if not hasattr(message, 'entities') or not message.entities:
            return message.text
            
        text = message.text
        formatted_text = ""
        last_position = 0
        
        # Sort entities by position to process them in order
        sorted_entities = sorted(message.entities, key=lambda e: e.offset)
        
        for entity in sorted_entities:
            # Add text before current entity
            formatted_text += text[last_position:entity.offset]
            
            # Extract the entity text
            entity_text = text[entity.offset:entity.offset + entity.length]
            
            # Handle different entity types
            if entity.type == 'url':
                formatted_text += f"[{entity_text}]({entity_text})"
            elif entity.type == 'text_link':
                formatted_text += f"[{entity_text}]({entity.url})"
            elif entity.type in ['bold', 'italic', 'code', 'pre']:
                formatted_text += entity_text  # Keep as is for now
            else:
                formatted_text += entity_text
                
            # Update last position
            last_position = entity.offset + entity.length
            
        # Add remaining text
        formatted_text += text[last_position:]
        
        return formatted_text
    
    def register_handlers(self):
        """Register message handlers"""
        @self.bot.message_handler(commands=['start'])
        def start_command(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_mode": False
                }
            
            self.bot.reply_to(
                message, 
                f"Hello {message.from_user.first_name}! I'm an AI assistant powered by OpenAI.\n"
                f"Use /ask followed by your question to interact with me.\n"
                f"Type /help to see all available commands."
            )
        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                return
                
            self.bot.reply_to(
                message,
                "Here are the available commands:\n"
                "/start - Start the conversation\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/stats - Show your usage statistics\n"
                "/ask - Ask me a question (e.g., /ask What's the weather like?)\n"
                "/listen - Start listening to all messages in the chat"
            )
        
        @self.bot.message_handler(commands=['model'])
        def model_command(message):
            if not self.is_authorized_chat(message):
                return
                
            self.bot.reply_to(
                message,
                f"Current model: {self.agent_config['model']}\n"
                f"Temperature: {self.agent_config['temperature']}\n"
                f"Max tokens: {self.agent_config['max_tokens']}"
            )
        
        @self.bot.message_handler(commands=['stats'])
        def stats_command(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            if user_id in self.active_users:
                user_data = self.active_users[user_id]
                message_count = len(user_data["history"])
                self.bot.reply_to(
                    message,
                    f"Your statistics:\n"
                    f"Messages sent: {message_count}"
                )
            else:
                self.bot.reply_to(
                    message,
                    "No statistics available. Start a conversation first with /ask."
                )

        @self.bot.message_handler(commands=['ask'])
        def ask_command(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_mode": False
                }
            
            # Extract the question from the message (remove /ask)
            if ' ' in message.text:
                question = message.text.split(' ', 1)[1]
            else:
                self.bot.reply_to(message, "Please provide a question after /ask")
                return
            
            # Process the question
            self.process_message(message, question)
        
        @self.bot.message_handler(commands=['listen'])
        def listen_command(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_mode": False
                }
            
            # Toggle listening mode
            self.active_users[user_id]["listening_mode"] = not self.active_users[user_id].get("listening_mode", False)
            
            if self.active_users[user_id]["listening_mode"]:
                self.bot.reply_to(message, "I am now listening to all messages in this chat. I will respond to any message automatically.")
            else:
                self.bot.reply_to(message, "Listening mode disabled. I will only respond to direct commands now.")
        
        # Only respond to direct messages (not in groups) that aren't commands
        @self.bot.message_handler(func=lambda message: message.chat.type == 'private' and not message.text.startswith('/'))
        def handle_direct_message(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_mode": False
                }
            
            # Process the direct message
            self.process_message(message, message.text)
        
        # Handle all messages in groups where bot is mentioned or in reply to bot's message
        @self.bot.message_handler(func=lambda message: (
            message.chat.type in ['group', 'supergroup'] and 
            (message.reply_to_message and message.reply_to_message.from_user.id == self.bot.get_me().id or
             self.bot.get_me().username and f"@{self.bot.get_me().username}" in message.text)
        ))
        def handle_group_mention(message):
            if not self.is_authorized_chat(message):
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_mode": False
                }
                
            # Extract text (remove bot mention if present)
            text = message.text
            if self.bot.get_me().username and f"@{self.bot.get_me().username}" in text:
                text = text.replace(f"@{self.bot.get_me().username}", "").strip()
                
            # Process the message
            self.process_message(message, text)
            
        # Handle all new messages when in listening mode
        @self.bot.message_handler(func=lambda message: 
            message.from_user.id in self.active_users and 
            self.active_users[message.from_user.id].get("listening_mode", False) and
            not message.text.startswith('/')
        )
        def handle_all_messages(message):
            if not self.is_authorized_chat(message):
                return
                
            # Process all messages when in listening mode
            self.process_message(message, message.text)
    
    def process_message(self, message, question_text):
        """Process user messages through the agent manager"""
        # Reload environment variables before each request
        load_dotenv(override=True)
        
        user_id = message.from_user.id
        
        # Process entities if present in the original message
        if hasattr(message, 'entities') and message.entities:
            question_text = self.extract_entities(message)
        
        # Store the question in history
        self.active_users[user_id]["history"].append({"role": "user", "content": question_text})
        
        # Reinitialize settings and agent manager with fresh env variables
        self.settings = Settings()
        self.agent_config = self.settings.get_agent_config()
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Send "typing" action
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            # Show a waiting message
            waiting_msg = self.bot.reply_to(message, "Processing your request...")
            
            # Process message through agent (async call in a sync context)
            import asyncio
            # Use robust message processing with retries and fallbacks
            response = asyncio.run(self.agent_manager.process_message_robust(
                message=question_text,
                streaming=False  # Non-streaming mode
            ))
            
            # Store response in history
            self.active_users[user_id]["history"].append({"role": "assistant", "content": response})
            
            # Extract trace URL from response
            trace_url = None
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                trace_url = parts[0].replace("View trace: ", "")
                response = parts[1] if len(parts) > 1 else ""
            
            # Delete waiting message and send response
            self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            self.bot.reply_to(message, response)
            
            # Send trace URL separately if available
            if trace_url:
                self.bot.send_message(
                    message.chat.id,
                    f"[View interaction trace]({trace_url})",
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            error_message = str(e)
            error_details = getattr(e, 'details', None)
            
            if error_details:
                if error_details.get('type') == 'OpenAIError':
                    error_message = (
                        f"OpenAI API Error:\n"
                        f"Message: {error_details.get('message')}\n"
                        f"Request ID: {error_details.get('request_id')}\n"
                        f"Status Code: {error_details.get('status_code')}"
                    )
                else:
                    error_message = (
                        f"Error Type: {error_details.get('type')}\n"
                        f"Message: {error_details.get('message')}"
                    )
            
            logger.error(f"Error processing message: {error_message}", exc_info=True)
            
            try:
                # Try to delete the waiting message if it exists
                self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            except:
                pass
            
            self.bot.reply_to(
                message,
                f"Sorry, there was an error processing your request:\n\n{error_message}\n\n"
                "You can try:\n"
                "1. Rephrasing your question\n"
                "2. Waiting a few moments and trying again\n"
                "3. Using /model to check current settings"
            )
    
    def run(self):
        """Run the Telegram bot."""
        logger.info("Starting Telegram bot using pyTelegramBotAPI in non-streaming mode")
        self.bot.infinity_polling()

def main():
    """Entry point for the Telegram interface."""
    try:
        bot_handler = TelegramBotHandler()
        bot_handler.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 