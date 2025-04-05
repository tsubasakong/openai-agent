## requirements
use openai agent sdk with mcp server to build ai agent what receive input prompt from terminal that type by user, and running the agent, then return the results to users.

- For the openai agent sdk with mcp chck this document https://openai.github.io/openai-agents-python/mcp/. 
- The mcp is in stdio mode with the config below

```
"mcp-proxy-agent-1": {
      "command": "/Users/frankhe/.local/bin/mcp-proxy",
      "args": [
        "https://sequencer-v2.heurist.xyz/mcp/sse"
      ]
    }
```

- the agent return could be either in streaming mode or not streaming mode
- for the agent with mcp ,check the example 
- Caching the tools by "to automatically cache the list of tools, you can pass cache_tools_list=True"
- https://github.com/openai/openai-agents-python/tree/main/examples/mcp/filesystem_example
- enable the tracing feature for this agent

