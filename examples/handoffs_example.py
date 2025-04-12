#!/usr/bin/env python3

import os
import sys
import asyncio
import time
import re
from dotenv import load_dotenv
from pydantic import BaseModel

# Add parent directory to Python path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agent import AgentManager, GuardrailFunctionOutput, AgentError
from src.config.settings import Settings
from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    ModelBehaviorError,
    UserError,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered
)

# Load environment variables
load_dotenv()

# Define output models for guardrails
class SafetyCheckOutput(BaseModel):
    is_safe: bool
    reasoning: str

async def safety_check_function(ctx, agent, input_data):
    """
    A guardrail that checks if the user input is safe and appropriate.
    """
    # Create an agent manager for the safety check
    safety_checker = AgentManager(
        model="gpt-4o-mini",  # Use a smaller model for guardrails to save costs
        temperature=0.0,      # Low temperature for consistent responses
        max_tokens=50000,      # Smaller response size needed
        instructions="You are a content safety checker. Your only job is to determine if the user input contains harmful, illegal, or inappropriate content. Return TRUE for is_safe if the content is safe, FALSE otherwise."
    )
    
    # Process the input with the safety checker
    safety_result_json = await safety_checker.process_message_robust(
        message=f"Please evaluate this input for safety: '{input_data}'",
        streaming=False
    )
    
    # Extract the JSON part from the response
    import json
    import re
    
    # Try to find and parse JSON in the response
    json_match = re.search(r'({.*})', safety_result_json, re.DOTALL)
    if json_match:
        try:
            safety_data = json.loads(json_match.group(1))
            safety_output = SafetyCheckOutput(
                is_safe=safety_data.get('is_safe', True),
                reasoning=safety_data.get('reasoning', "No reasoning provided")
            )
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            safety_output = SafetyCheckOutput(
                is_safe=True,
                reasoning="Failed to parse safety check result, defaulting to safe."
            )
    else:
        # Simple parsing fallback
        is_safe = "not harmful" in safety_result_json.lower() or "is safe" in safety_result_json.lower()
        safety_output = SafetyCheckOutput(
            is_safe=is_safe,
            reasoning=f"Simple text analysis of safety check: {'Safe' if is_safe else 'Potentially unsafe'}"
        )
    
    return GuardrailFunctionOutput(
        output_info=safety_output,
        tripwire_triggered=not safety_output.is_safe
    )

def print_error_details(error):
    """Print formatted error details"""
    print("\n" + "="*50)
    print("ERROR DETAILS:")
    print("="*50)
    
    if isinstance(error, AgentError):
        print(f"Error message: {str(error)}")
        
        if error.details:
            print("\nAdditional details:")
            for key, value in error.details.items():
                print(f"  {key}: {value}")
            
            # Print suggestions if available
            if "suggestion" in error.details:
                print("\nSuggested solution:")
                print(f"  {error.details['suggestion']}")
                
        print(f"\nRetriable: {error.retriable}")
    else:
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {str(error)}")
        
    print("="*50)
    print("TROUBLESHOOTING TIPS:")
    print("-"*50)
    print("1. If it's a 500 server error, try splitting your complex query into multiple simpler ones")
    print("2. If it's a ModelBehaviorError, your query might be too complex for the model to handle")
    print("3. If it's a MaxTurnsExceeded error, the conversation reached maximum allowed back-and-forth")
    print("4. For tool-related errors, make sure all necessary MCP tools are available")
    print("5. For guardrail issues, check if your content complies with safety guidelines")
    print("="*50)

def contains_question(text):
    """Check if text likely contains a question that needs user input"""
    # Remove the trace URL part
    if "View trace:" in text:
        text = text.split("\n\n", 1)[1] if "\n\n" in text else text
        
    # Check for question marks
    if "?" in text:
        return True
    
    # Check for common question phrases
    question_patterns = [
        r"could you (please )?(specify|clarify|provide|tell me)",
        r"(can|would) you (please )?(specify|clarify|provide|tell me)",
        r"(please )?(specify|clarify|provide|tell me)",
        r"what (specific|particular|exact)",
        r"which (specific|particular|exact)"
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, text.lower()):
            return True
            
    return False

async def handle_interactive_query(agent, query, context_update=None):
    """Process a query with support for interactive follow-up questions"""
    try:
        conversation_active = True
        current_query = query
        conversation_context = context_update or {}
        
        # Store the final response
        final_response = None
        
        while conversation_active:
            print(f"\nProcessing: {current_query}")
            print("-" * 50)
            
            # Process the query
            start_time = time.time()
            response = await agent.process_message_robust(
                message=current_query,
                streaming=False,
                context_update=conversation_context
            )
            processing_time = time.time() - start_time
            
            # Print the response
            print(f"\nResponse (processed in {processing_time:.2f} seconds):")
            print(response)
            
            # Update the final response
            final_response = response
            
            # Check if the response contains a question requiring follow-up
            if contains_question(response):
                print("\n" + "-"*50)
                print("The agent is asking for clarification. Would you like to respond? (y/n)")
                should_continue = input("> ")
                
                if should_continue.lower() == 'y':
                    print("\nPlease provide your clarification:")
                    follow_up = input("> ")
                    current_query = follow_up
                    # Clear context_update after first message to avoid re-applying it
                    conversation_context = None
                else:
                    print("\nEnding the conversation.")
                    conversation_active = False
            else:
                # No question in the response, end the conversation
                conversation_active = False
                
        return final_response
        
    except Exception as e:
        print_error_details(e)
        return None

async def main():
    """Main example function showing handoffs and guardrails."""
    settings = Settings()
    
    # Create specialized agents for handoffs with tool list caching enabled
    
    # On-chain analysis specialist agent for Solana meme coins
    onchain_agent = AgentManager(
        model=settings.default_model,
        temperature=0.1,
        max_tokens=settings.max_tokens,
        mcp_proxy_command=settings.mcp_proxy_command,
        mcp_proxy_url=settings.mcp_proxy_url,
        enable_mcp_cache=True,  # Enable caching for tool list
        instructions="""You are a Solana meme coin on-chain analysis specialist. 
Your job is to analyze and identify trending meme coins on Solana blockchain using on-chain data and metrics.

When analyzing meme coins, focus on:
1. Transaction volume, frequency, and patterns
2. Holder distribution and wallet concentration
3. Smart contract activities and token transfers
4. Liquidity metrics in DEXs (Jupiter, Raydium, Orca)
5. Token burn rates and supply dynamics
6. Recent token listing events
7. Whale movements and accumulation patterns
8. Trading volume spikes and unusual activities

When reporting findings:
- Present data in a structured format showing coin name, symbol, and key metrics
- Highlight tokens showing unusual transaction volume or holder growth
- Compare current activity to historical patterns
- Identify tokens with significant recent changes in on-chain metrics
- Assess liquidity depth and trading volumes across DEXs
- Evaluate contract interactions and token transfer patterns

Always prioritize objective on-chain data over subjective opinions about meme coins.
"""
    )
    
    # Twitter social analysis specialist agent for Solana meme coins
    twitter_agent = AgentManager(
        model=settings.default_model,
        temperature=0.7,  # Higher temperature for more creative social analysis
        max_tokens=settings.max_tokens,
        mcp_proxy_command=settings.mcp_proxy_command,
        mcp_proxy_url=settings.mcp_proxy_url,
        enable_mcp_cache=True,  # Enable caching for tool list
        instructions="""You are a Solana meme coin social signal analyst.
Your job is to analyze social media trends, sentiment, and engagement patterns related to Solana meme coins.

When analyzing social signals for meme coins, focus on:
1. Twitter engagement metrics (likes, retweets, replies)
2. Trending hashtags related to specific meme coins
3. Influential accounts discussing specific Solana tokens
4. Sentiment analysis of discussions (positive, negative, neutral)
5. Change in social activity over time (increasing/decreasing)
6. Community growth and participation metrics
7. Social volume compared to price action correlation
8. Identifying early viral coins with growing social presence

When reporting findings:
- Present data showing coin name, social metrics, and sentiment scores
- Identify which meme coins are gaining the most social traction
- Highlight emerging trends or narratives around specific tokens
- Compare social sentiment across different meme coins
- Assess correlation between social activity and on-chain activity
- Evaluate authenticity of engagement (organic vs. artificial)

Always analyze social signals in context with broader market trends and Solana ecosystem developments.
"""
    )
    
    # Create main agent with handoffs - optimized for meme coin analysis
    main_agent = AgentManager(
        model=settings.default_model,
        temperature=0.3,
        max_tokens=settings.max_tokens,
        mcp_proxy_command=settings.mcp_proxy_command,
        mcp_proxy_url=settings.mcp_proxy_url,
        enable_mcp_cache=True,  # Enable tool list caching for better performance
        enable_guardrails=False,  # Disable guardrails by default for meme coin analysis
        instructions="""You are a specialized Solana meme coin analyst who integrates both on-chain data and social signals.

Your expertise is finding alpha in the Solana meme coin ecosystem by combining:
1. On-chain blockchain data - smart contract activity, holder metrics, liquidity data
2. Social media signals - Twitter engagement, sentiment, community growth, influencer activity

For comprehensive meme coin analysis:
- When users ask about trending tokens or specific meme coins on Solana, hand off to the on-chain specialist
- When users ask about Twitter discussions, sentiment, or social trends, hand off to the social signal specialist
- For queries involving both aspects, coordinate data from both specialists to provide an integrated analysis

When analyzing meme coins, always:
- Prioritize DATA over hype - both on-chain metrics and quantifiable social signals
- Look for correlation between social momentum and on-chain activity
- Identify coins with genuine community growth rather than artificial pumps
- Compare current meme coin patterns with historical successful launches
- Highlight both bullish and bearish signals for each token discussed

Provide your analysis in a structured format with clear section headers for on-chain data, social signals, and integrated analysis.
Use the language style of a data-driven crypto analyst - professional but not overly formal.
"""
    )
    
    # Create and add the safety guardrail
    safety_guardrail = main_agent.create_guardrail(safety_check_function)
    main_agent.add_guardrail(safety_guardrail)
    
    # Add handoffs to the main agent
    main_agent.add_handoff(onchain_agent)
    main_agent.add_handoff(twitter_agent)
    
    # Get query from command line if provided, otherwise use default
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        # Default queries to test
        queries = [
            "What are the trending meme coins on Solana right now and what's the social sentiment around them?",
            # Add more queries here for testing
        ]
        user_query = queries[0]
    
    print(f"\n\nProcessing query: {user_query}")
    print("-" * 50)
    
    # Try to separate the complex query into parts if it contains "and"
    if " and " in user_query.lower() and len(user_query) > 60:
        print("\nThis seems to be a complex query. Would you like to split it into separate queries? (y/n)")
        split_choice = input("> ")
        
        if split_choice.lower() == 'y':
            parts = user_query.split(" and ", 1)
            queries = [part.strip() for part in parts]
            
            print("\nSplitting into:")
            for i, part in enumerate(queries):
                print(f"{i+1}. {part}")
            
            # Process each part separately with support for follow-up questions
            combined_response = ""
            first_part_result = None
            
            # Process first part
            print(f"\n\nProcessing part 1: {queries[0]}")
            print("-" * 50)
            first_part_result = await handle_interactive_query(main_agent, queries[0])
            if first_part_result:
                combined_response += f"\n\nPart 1: {first_part_result}"
                
                # Extract token names from the first result to help with the second query
                tokens_mentioned = []
                if "trending" in queries[0].lower() or "meme coin" in queries[0].lower():
                    # Try to extract token names and symbols 
                    # Modified regex to better match meme coin formatting
                    token_matches = re.findall(r'\*\*([^*]+)\*\*\s*\(([^)]+)\)', first_part_result)
                    if not token_matches:
                        # Try alternative format (Name (SYMBOL))
                        token_matches = re.findall(r'([A-Za-z\s]+)\s*\(([A-Z0-9]+)\)', first_part_result)
                    if token_matches:
                        tokens_mentioned = [f"{name.strip()} ({symbol.strip()})" for name, symbol in token_matches]
                
            # Process second part with context from first part if applicable
            print(f"\n\nProcessing part 2: {queries[1]}")
            print("-" * 50)
            
            # If first part mentioned tokens, include them as context for the second part
            enhanced_query = queries[1]
            if tokens_mentioned and ("twitter" in queries[1].lower() or "social" in queries[1].lower() or "sentiment" in queries[1].lower()):
                token_list = ", ".join(tokens_mentioned[:3])  # Take first 3 tokens
                enhanced_query = f"{queries[1]} Specifically looking for information about {token_list} mentioned in the previous analysis."
                print(f"\nEnhanced query with token context: {enhanced_query}")
            else:
                print(f"\nUsing original query: {enhanced_query}")
                
            second_part_result = await handle_interactive_query(main_agent, enhanced_query)
            if second_part_result:
                combined_response += f"\n\nPart 2: {second_part_result}"
            
            print("\n\nCombined responses:")
            print("-" * 50)
            print(combined_response)
            return
    
    # Process the full query with interactive follow-up support
    await handle_interactive_query(main_agent, user_query)

if __name__ == "__main__":
    asyncio.run(main()) 