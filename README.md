# OpenAI Agent with MCP Server

A modular implementation of an OpenAI agent using the OpenAI Agents SDK with support for multiple interfaces:
- Command-line interface
- Telegram bot interface

The agent can use multiple tools to answer questions and solve complex tasks, planning its approach by chaining together multiple tool calls before providing a final answer.

## Features

- **Modular Design**: Clean separation of concerns using OOD principles
- **Multiple Interfaces**: Choose between CLI and Telegram interfaces
- **Streaming Responses**: Real-time response streaming in CLI mode
- **Configurable**: Customizable model, temperature, and other settings
- **Tracing**: Integrated with OpenAI's tracing system for debugging

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd openai-agent
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Edit the `.env` file and add your OpenAI API key and other configuration options.

## Usage

### Command-Line Interface

Run the agent in the terminal:

```
python src/main.py [options]
```

Options:
- `--no-stream`: Disable streaming mode (responses appear all at once)
- `--model MODEL`: Specify the OpenAI model to use (default: gpt-4o)
- `--temperature TEMP`: Set the model temperature (default: 0.1)
- `--max-tokens TOKENS`: Set the maximum number of tokens (default: 2000)

Once running, you can interact with the agent by typing messages. Type `exit` or `quit` to end the session.

### Telegram Bot Interface

To use the Telegram interface, you need to:

1. Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get your token
2. Add the token to your `.env` file as `TELEGRAM_BOT_TOKEN`
3. Optionally, add a comma-separated list of allowed user IDs as `TELEGRAM_ALLOWED_USERS`

Then run:

```
python src/main.py --telegram
```

The bot will start and you can interact with it on Telegram.

## Project Structure

```
openai-agent/
├── .env                     # Environment variables
├── .env.example             # Example environment variables
├── requirements.txt         # Project dependencies
├── README.md                # Project documentation
└── src/                     # Source code
    ├── core/                # Core functionality
    │   └── agent.py         # Agent manager
    ├── config/              # Configuration
    │   └── settings.py      # Settings manager
    ├── interfaces/          # User interfaces
    │   ├── cli/             # Command-line interface
    │   │   └── terminal.py  # Terminal UI
    │   └── telegram/        # Telegram interface
    │       └── bot.py       # Telegram bot
    ├── utils/               # Utility functions
    └── main.py              # Main entry point
```

## Extending the Application

### Adding a New Interface

To add a new interface (e.g., Web API, Discord bot):

1. Create a new package under `src/interfaces/`
2. Implement the interface using the `AgentManager` from `src/core/agent.py`
3. Update `src/main.py` to include the new interface

### Customizing Agent Behavior

To customize how the agent operates:

1. Modify the `AgentManager` class in `src/core/agent.py`
2. Update the instructions or model settings as needed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 

# OpenAI Agent with Telegram Bot

This project implements an AI assistant using the OpenAI API and provides a Telegram bot interface.

## Setup

1. Create a Python virtual environment:
   ```
   python -m venv .venv
   ```

2. Activate the virtual environment:
   ```
   # On macOS/Linux
   source .venv/bin/activate
   
   # On Windows
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

## Running the Telegram Bot

To run the Telegram bot in non-streaming mode:

```
python telebot_version.py
```

### Bot Commands

The bot supports the following commands:
- `/start` - Start the bot
- `/help` - Show available commands
- `/model` - Show current model settings
- `/stats` - Show conversation statistics
- `/ask [question]` - Ask a question to the AI assistant

In private chats, the bot responds to all messages. In group chats, it only responds to messages that start with `/ask`.

For more detailed instructions, see [TELEGRAM_BOT_GUIDE.md](TELEGRAM_BOT_GUIDE.md).

## Features

- Chat with OpenAI assistants via Telegram
- Supports both text and file sharing
- Command support (/start, /help, /model, /stats)
- User authentication

## CLI Mode

To run the CLI version of the assistant:

```
python src/main.py
``` 