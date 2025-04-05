# Telegram Bot Guide

This document explains how to set up and use the Telegram bot with the OpenAI Agent.

## Setup

1. Create a Telegram bot:
   - Open Telegram and search for [@BotFather](https://t.me/BotFather)
   - Start a chat and send `/newbot`
   - Follow the instructions to create a new bot
   - Once completed, you'll receive a token (keep this secure!)

2. Add the bot token to your `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Run the bot:
   ```
   python telebot_version.py
   ```

## Using the Bot

### Commands

The bot supports the following commands:

- `/start` - Start the bot and get a welcome message
- `/help` - Display available commands
- `/model` - Show the current AI model configuration
- `/stats` - View your usage statistics
- `/ask [question]` - Ask a question to the AI assistant

### Private Chats vs. Groups

- **Private chats**: In direct messages with the bot, you can either use `/ask` or simply type your message directly
- **Group chats**: In groups, the bot will only respond to messages that begin with `/ask`

### Examples

#### Private Chat
```
You: Hello
Bot: [responds with an answer]

You: /ask What is artificial intelligence?
Bot: [responds with an answer about AI]
```

#### Group Chat
```
You: Hello
Bot: [no response]

You: /ask What is artificial intelligence?
Bot: [responds with an answer about AI]
```

## Troubleshooting

If the bot is not responding:

1. Ensure the bot is running (`python telebot_version.py`)
2. Check that you have the correct bot token in your `.env` file
3. Verify that your OpenAI API key is valid
4. Make sure you're using the correct command format (especially in groups)

## Advanced Configuration

You can modify the bot's behavior by editing the `telebot_version.py` file:

- Change response formatting
- Add new commands
- Modify the conversation history management
- Adjust user authentication settings 