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