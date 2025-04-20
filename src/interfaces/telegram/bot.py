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
        # Force reload settings to ensure we have the latest environment variables
        self.settings = Settings(force_reload=True)
        self.agent_config = self.settings.get_agent_config()
        
        logger.info(f"TelegramBotHandler initialized with chat IDs: {self.settings.telegram_chat_id}")
        
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
            telebot.types.BotCommand("listen", "Start listening to all messages in the chat"),
            telebot.types.BotCommand("status", "Check listening mode status"),
            telebot.types.BotCommand("debug", "Debug the bot configuration")
        ]
        self.bot.set_my_commands(commands)
    
    def is_authorized_chat(self, message):
        """Check if the message is from an authorized chat"""
        # If chat_id is None, don't authorize any chats
        if self.chat_id is None:
            logger.info(f"No authorized chat IDs configured")
            return False
        
        msg_chat_id = int(message.chat.id)
        # Debug the types and values
        logger.info(f"Authorization check - Message chat_id: {msg_chat_id} (type: {type(msg_chat_id)})")
        logger.info(f"Authorization check - Allowed chat_ids: {self.chat_id} (type: {type(self.chat_id)})")
        
        # Check each chat ID individually for debugging
        for allowed_id in self.chat_id:
            logger.info(f"Comparing {msg_chat_id} with allowed ID {allowed_id} (type: {type(allowed_id)}): {msg_chat_id == allowed_id}")
        
        is_authorized = msg_chat_id in self.chat_id
        logger.info(f"Final authorization result for chat {msg_chat_id}: {is_authorized}")
        return is_authorized
    
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
    
    def extract_command(self, text):
        """Extract the command from a message text, handling commands with bot username"""
        if not text:
            return None
            
        # Split the text by the first space
        parts = text.split(' ', 1)
        command = parts[0]
        
        # Remove the bot username suffix if present
        if '@' in command:
            command = command.split('@', 1)[0]
            
        return command
    
    def handle_command(self, message, command_text):
        """Generic handler for commands, including those with bot username"""
        # Extract the base command (remove bot username if present)
        command = self.extract_command(command_text)
        if not command:
            return False  # Not a command
            
        # Remove the leading slash
        command = command[1:] if command.startswith('/') else command
        
        # Handle each command
        if command == 'debug':
            self.handle_debug_command(message)
            return True
        elif command == 'start':
            self.handle_start_command(message)
            return True
        elif command == 'help':
            self.handle_help_command(message)
            return True
        elif command == 'model':
            self.handle_model_command(message)
            return True
        elif command == 'stats':
            self.handle_stats_command(message)
            return True
        elif command == 'listen':
            self.handle_listen_command(message)
            return True
        elif command == 'status':
            self.handle_status_command(message)
            return True
        elif command == 'ask':
            self.handle_ask_command(message)
            return True
            
        return False  # Command not recognized
        
    def handle_debug_command(self, message):
        """Handle the /debug command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /debug command")
            return
        
        # Refresh settings to ensure we have the latest
        self.settings = Settings.reload()
        self.chat_id = self.settings.telegram_chat_id
        
        debug_info = [
            f"Bot username: @{self.bot.get_me().username}",
            f"Current chat ID: {message.chat.id}",
            f"Chat type: {message.chat.type}",
            f"Authorized chat IDs: {self.chat_id}",
            f"Is authorized: {int(message.chat.id) in self.chat_id}",
            f"Active users: {len(self.active_users)}",
            f"OpenAI model: {self.agent_config['model']}"
        ]
        
        self.bot.reply_to(message, "\n".join(debug_info))
        
    def handle_start_command(self, message):
        """Handle the /start command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /start command")
            return
            
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": message.from_user.first_name,
                "username": message.from_user.username,
                "history": [],
                "listening_chats": set()  # Track chats where listening is enabled for this user
            }
        
        self.bot.reply_to(
            message, 
            f"Hello {message.from_user.first_name}! I'm an AI assistant powered by OpenAI.\n"
            f"Use /ask followed by your question to interact with me.\n"
            f"Type /help to see all available commands."
        )
        
    def handle_help_command(self, message):
        """Handle the /help command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /help command")
            return
            
        self.bot.reply_to(
            message,
            "Here are the available commands:\n"
            "/start - Start the conversation\n"
            "/help - Show this help message\n"
            "/model - Show the current AI model\n"
            "/stats - Show your usage statistics\n"
            "/ask - Ask me a question (e.g., /ask What's the weather like?)\n"
            "/listen - Toggle listening to all messages in this chat\n"
            "/status - Check listening mode status\n"
            "/debug - Show debug information"
        )
        
    def handle_model_command(self, message):
        """Handle the /model command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /model command")
            return
            
        self.bot.reply_to(
            message,
            f"Current model: {self.agent_config['model']}\n"
            f"Temperature: {self.agent_config['temperature']}\n"
            f"Max tokens: {self.agent_config['max_tokens']}"
        )
        
    def handle_stats_command(self, message):
        """Handle the /stats command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /stats command")
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
            
    def handle_listen_command(self, message):
        """Handle the /listen command"""
        logger.info(f"Processing /listen command in chat {message.chat.id} ({message.chat.type})")
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /listen command")
            return
            
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": message.from_user.first_name,
                "username": message.from_user.username,
                "history": [],
                "listening_chats": set()
            }
        
        # Make sure listening_chats exists
        if "listening_chats" not in self.active_users[user_id]:
            self.active_users[user_id]["listening_chats"] = set()
            
        # Toggle listening mode for this specific chat
        if chat_id in self.active_users[user_id]["listening_chats"]:
            self.active_users[user_id]["listening_chats"].remove(chat_id)
            listening_mode = False
        else:
            self.active_users[user_id]["listening_chats"].add(chat_id)
            listening_mode = True
            
        logger.info(f"User {user_id} listening mode for chat {chat_id}: {listening_mode}")
        logger.info(f"User's active listening chats: {self.active_users[user_id]['listening_chats']}")
        
        if listening_mode:
            self.bot.reply_to(message, "I am now listening to all messages in this chat. I will respond to any message automatically.")
        else:
            self.bot.reply_to(message, "Listening mode disabled. I will only respond to direct commands now.")
            
    def handle_ask_command(self, message):
        """Handle the /ask command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /ask command")
            return
            
        user_id = message.from_user.id
        
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": message.from_user.first_name,
                "username": message.from_user.username,
                "history": [],
                "listening_chats": set()
            }
        
        # Extract the question from the message (remove /ask)
        if ' ' in message.text:
            question = message.text.split(' ', 1)[1]
        else:
            self.bot.reply_to(message, "Please provide a question after /ask")
            return
        
        # Process the question
        self.process_message(message, question)
    
    def handle_status_command(self, message):
        """Handle the /status command"""
        if not self.is_authorized_chat(message):
            return
            
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if (user_id in self.active_users and 
            "listening_chats" in self.active_users[user_id]):
            is_listening = chat_id in self.active_users[user_id]["listening_chats"]
            status_msg = f"Listening mode is {'ON' if is_listening else 'OFF'} for this chat.\n\n"
            
            if is_listening:
                status_msg += "I will automatically respond to all messages in this chat."
            else:
                status_msg += "I will only respond to commands or when mentioned."
                
            # Show global listening status
            all_listening_chats = []
            for user, data in self.active_users.items():
                if "listening_chats" in data and data["listening_chats"]:
                    all_listening_chats.extend(data["listening_chats"])
                    
            if all_listening_chats:
                status_msg += f"\n\nListening is active in {len(set(all_listening_chats))} chat(s) total."
        else:
            status_msg = "Listening mode is not configured. Use /listen to enable it."
            
        self.bot.reply_to(message, status_msg)
    
    def register_handlers(self):
        """Register message handlers"""
        # Debug handler to log all incoming messages
        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def debug_handler(message):
            try:
                logger.info(f"Received message '{message.text}' in chat {message.chat.id} ({message.chat.type}) from {message.from_user.username or message.from_user.id}")
                
                # Try to handle as a command if it starts with /
                if message.text and message.text.startswith('/'):
                    if self.handle_command(message, message.text):
                        return
                        
                # For non-commands, check if listening mode is enabled for this chat
                user_id = message.from_user.id
                chat_id = message.chat.id
                
                if (self.is_authorized_chat(message) and
                    user_id in self.active_users and
                    "listening_chats" in self.active_users[user_id] and
                    chat_id in self.active_users[user_id]["listening_chats"]):
                    logger.info(f"Processing message in listening mode from {user_id} in chat {chat_id}: '{message.text}'")
                    self.process_message(message, message.text)
                    return
                    
            except Exception as e:
                logger.error(f"Error in debug_handler: {str(e)}", exc_info=True)
                
            # Let other handlers process the message
            pass
            
        @self.bot.message_handler(commands=['start'])
        def start_command(message):
            logger.info(f"Received /start command in chat {message.chat.id}")
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /start command")
                return
                
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_chats": set()  # Track chats where listening is enabled for this user
                }
            
            self.bot.reply_to(
                message, 
                f"Hello {message.from_user.first_name}! I'm an AI assistant powered by OpenAI.\n"
                f"Use /ask followed by your question to interact with me.\n"
                f"Type /help to see all available commands."
            )
        
        @self.bot.message_handler(commands=['debug'])
        def debug_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /debug command")
                return
            
            # Refresh settings to ensure we have the latest
            self.settings = Settings.reload()
            self.chat_id = self.settings.telegram_chat_id
            
            debug_info = [
                f"Bot username: @{self.bot.get_me().username}",
                f"Current chat ID: {message.chat.id}",
                f"Chat type: {message.chat.type}",
                f"Authorized chat IDs: {self.chat_id}",
                f"Is authorized: {int(message.chat.id) in self.chat_id}",
                f"Active users: {len(self.active_users)}",
                f"OpenAI model: {self.agent_config['model']}"
            ]
            
            self.bot.reply_to(message, "\n".join(debug_info))
        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /help command")
                return
                
            self.bot.reply_to(
                message,
                "Here are the available commands:\n"
                "/start - Start the conversation\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/stats - Show your usage statistics\n"
                "/ask - Ask me a question (e.g., /ask What's the weather like?)\n"
                "/listen - Toggle listening to all messages in this chat\n"
                "/status - Check listening mode status\n"
                "/debug - Show debug information"
            )
        
        @self.bot.message_handler(commands=['model'])
        def model_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /model command")
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
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /stats command")
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
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /ask command")
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_chats": set()
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
            logger.info(f"Received /listen command in chat {message.chat.id} ({message.chat.type})")
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /listen command")
                return
                
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_chats": set()
                }
            
            # Make sure listening_chats exists
            if "listening_chats" not in self.active_users[user_id]:
                self.active_users[user_id]["listening_chats"] = set()
                
            # Toggle listening mode for this specific chat
            if chat_id in self.active_users[user_id]["listening_chats"]:
                self.active_users[user_id]["listening_chats"].remove(chat_id)
                listening_mode = False
            else:
                self.active_users[user_id]["listening_chats"].add(chat_id)
                listening_mode = True
            
            if listening_mode:
                self.bot.reply_to(message, "I am now listening to all messages in this chat. I will respond to any message automatically.")
            else:
                self.bot.reply_to(message, "Listening mode disabled. I will only respond to direct commands now.")
        
        # Only respond to direct messages (not in groups) that aren't commands
        @self.bot.message_handler(func=lambda message: message.chat.type == 'private' and not message.text.startswith('/'))
        def handle_direct_message(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} attempted direct message")
                return
                
            logger.info(f"Processing direct message from {message.from_user.id} in private chat: '{message.text}'")
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_chats": set()
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
                logger.warning(f"Unauthorized chat {message.chat.id} attempted group mention")
                return
                
            logger.info(f"Processing group mention from {message.from_user.id} in chat {message.chat.id}: '{message.text}'")
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": [],
                    "listening_chats": set()
                }
                
            # Extract text (remove bot mention if present)
            text = message.text
            if self.bot.get_me().username and f"@{self.bot.get_me().username}" in text:
                text = text.replace(f"@{self.bot.get_me().username}", "").strip()
                
            # Process the message
            self.process_message(message, text)
            
        # The debug_handler now handles messages in listening mode
    
    def process_message(self, message, question_text):
        """Process user messages through the agent manager"""
        # Reload environment variables before each request using Settings singleton
        self.settings = Settings.reload()
        
        user_id = message.from_user.id
        
        # Process entities if present in the original message
        if hasattr(message, 'entities') and message.entities:
            question_text = self.extract_entities(message)
        
        # Store the question in history
        self.active_users[user_id]["history"].append({"role": "user", "content": question_text})
        
        # Reinitialize agent manager with fresh settings
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
            
            # Remove trace URL from the response if present
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                # Keep only the actual response part
                response = parts[1] if len(parts) > 1 else ""
            
            # Store response in history (without trace URL)
            self.active_users[user_id]["history"].append({"role": "assistant", "content": response})
            
            # Delete waiting message and send response
            self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            self.bot.reply_to(message, response)
            
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