# OpenAI Agent SDK Optimizations

This document outlines the optimizations made to the codebase to better align with the OpenAI Agent SDK best practices.

## Key Improvements

### 1. Agent Handoffs

Added support for agent handoffs, allowing the main agent to route queries to specialized agents. This enables:

- Domain-specific agents that handle particular types of questions
- Better response quality through specialization
- More efficient use of model resources by matching query complexity to appropriate models

```python
# Create specialized agents
math_agent = AgentManager(instructions="You are a math specialist...")
travel_agent = AgentManager(instructions="You are a travel specialist...")

# Add as handoffs to main agent
main_agent.add_handoff(math_agent)
main_agent.add_handoff(travel_agent)
```

### 2. Input Guardrails

Implemented support for input guardrails that can filter or modify user inputs before they reach the agent. Benefits include:

- Content safety filtering
- Query validation
- Input reformatting for better agent performance

```python
# Create and add a guardrail
safety_guardrail = main_agent.create_guardrail(safety_guardrail_function)
main_agent.add_guardrail(safety_guardrail)

# You can enable/disable guardrails dynamically
agent.disable_guardrails()  # Turn off guardrails without removing them
agent.enable_guardrails()   # Turn guardrails back on
```

### 3. Context Management

Added persistent context between agent calls to maintain conversation state. This enables:

- Memory across multiple interactions
- Stateful conversations
- User-specific customizations

```python
# Set initial context
response = await agent.process_message(
    message="Hello",
    context_update={"user_name": "Alice"}
)

# Later messages will have access to the context
response = await agent.process_message("What's my name?")
# Agent can access user_name from context
```

### 4. Tool List Caching

Implemented caching for MCP server tool lists to improve performance by reducing latency. Benefits include:

- Faster response times by avoiding repeated tool list fetching
- Improved user experience with quicker initial responses
- Configurable caching with ability to invalidate as needed

```python
# Create agent with tool list caching enabled
agent = AgentManager(
    enable_mcp_cache=True  # Default is True
)

# Invalidate the tool list cache when needed
agent.clear_cache()  # Calls invalidate_tools_cache() on the MCP server
```

### 5. More Robust API Usage

- Improved error handling with better retry mechanisms
- Support for fallback models when primary models are unavailable
- More configurable settings for temperature, tokens, etc.

### 6. Configurable Guardrails

Added the ability to enable or disable guardrails dynamically without removing the guardrail configuration:

- Toggle guardrails on/off during runtime
- Maintain guardrail configurations even when disabled
- Quickly switch between protected and unprotected operation modes

```python
# Create agent with guardrails enabled
agent = AgentManager(
    enable_guardrails=True  # Default is True
)

# Disable guardrails for specific scenarios
agent.disable_guardrails()

# Re-enable when needed
agent.enable_guardrails()
```

## Example Usage

See the `examples/handoffs_example.py` file for a complete demonstration of these optimizations. This example shows:

1. Creating specialized agents for different domains
2. Setting up handoffs between agents 
3. Implementing a safety guardrail
4. Using context persistence for multi-turn conversations
5. Demonstrating the performance benefits of tool list caching
6. Toggling guardrails on and off during runtime

## Best Practices

- Use specialized agents for specific domains to improve response quality
- Implement guardrails for safety and input validation
- Use context to maintain conversation state
- Set appropriate temperature and token limits for different use cases
- Enable tool list caching to improve performance, especially for stable tool sets
- Only disable guardrails in controlled environments or for trusted inputs
- Invalidate tool caches when tools have been updated
- Log trace IDs for debugging and monitoring

## Future Improvements

- Support for custom tools and tool arguments
- More sophisticated handoff logic with confidence scores
- Better logging and monitoring integration
- Enhanced guardrail capabilities with more output validation 