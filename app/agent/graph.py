import os
import asyncio
from contextlib import asynccontextmanager
from typing import cast
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.func import END, START
from langchain_mcp_adapters.client import MultiServerMCPClient
from .state import AgentState, EXPLORIUM_SYSTEM_PROMPT

@asynccontextmanager
async def create_explorium_langgraph(config: dict):
    """
    Creates a LangGraph with Explorium MCP tools.
    
    This is the core function that builds the MCP agent workflow graph.
    It sets up a connection to the Explorium MCP tools server, initializes
    the language model, and builds a graph with nodes for reasoning and tool execution.
    
    Args:
        config (dict): Configuration for the LangGraph, including API keys
        
    Returns:
        An async context manager that yields the compiled LangGraph
    
    Flow:
    1. Initialize MCP client to connect to Explorium's tool server
    2. Set up the language model (Claude)
    3. Define the reasoning node that processes messages
    4. Define the tools node that executes external tools
    5. Connect the nodes with appropriate edges
    6. Compile and return the graph
    """
    # Load .env file
    load_dotenv()
    print("Starting to create LangGraph...")
    
    # Get API keys from environment
    explorium_api_key = os.getenv("EXPLORIUM_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    
    # Strip whitespace from API key if present
    if anthropic_api_key:
        anthropic_api_key = anthropic_api_key.strip()

    if not explorium_api_key:
        raise ValueError("EXPLORIUM_API_KEY not found in environment variables. Please check your .env file.")
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables. Please check your .env file.")

    # --- Get paths from environment --- 
    uv_path = os.getenv("UV_PATH")
    working_dir = os.getenv("MCP_WORKING_DIR")

    if not uv_path:
        raise ValueError("UV_PATH not found in environment variables. Please check your .env file.")
    if not working_dir:
        raise ValueError("MCP_WORKING_DIR not found in environment variables. Please check your .env file.")
    # --- End get paths ---
    
    # Initialize the MCP client that connects to the Explorium tool server
    # As of langchain-mcp-adapters 0.1.0, MultiServerMCPClient cannot be used as a context manager
    # Use the new API: create client and await get_tools()
    client = MultiServerMCPClient({
        "explorium": {
            "transport": "stdio",  # Communication via standard input/output
            "command": uv_path,    # Path to the UV package runner
            "args": [              # Arguments to run the local MCP server
                "run",
                "--with",
                "mcp",
                "--with",
                "pydantic",
                "mcp",
                "run",
                f"{working_dir}/local_dev_server.py"
            ],
            "env": {               # Environment variables for the MCP server
                "EXPLORIUM_API_KEY": explorium_api_key
            },
        }
    })
    print("MCP client initialized...")
    
    # Load all available tools from the MCP server (await is required in 0.1.0+)
    tools = await client.get_tools()
    print(f"Loaded {len(tools) if tools else 0} tools")
    
    # Initialize the Claude language model with explicit API key
    # According to LangGraph documentation, passing api_key explicitly is recommended
    model = ChatAnthropic(
        model="claude-3-7-sonnet-20250219",
        temperature=0.7,
        api_key=anthropic_api_key
    )
        
        # Define the reasoning node function that processes messages using Claude
        async def reasoning_node(state: AgentState):
            """
            The reasoning node handles the AI's thinking and decision-making.
            
            This function:
            1. Binds the available tools to the language model
            2. Sends the current conversation state to Claude
            3. Returns the model's response with potential tool calls
            
            Args:
                state (AgentState): The current state containing messages history
                
            Returns:
                dict: Updated state with new AI message
            """
            # Bind tools to the model so it can use them
            bound_model = model.bind_tools(tools)
            system_prompt = SystemMessage(content=EXPLORIUM_SYSTEM_PROMPT)
            
            # Add a small delay to prevent rate limiting
            await asyncio.sleep(2)  # Rate limiting protection
            
            try:
                # Invoke the model with the current state
                response = cast(
                    AIMessage,
                    await bound_model.ainvoke(
                        [system_prompt, *state.messages],
                        config={
                            "max_retries": 2,
                            "timeout": 30,
                        }
                    ),
                )
                return {"messages": [response]}
            except Exception as e:
                # --- Add specific error logging --- 
                print(f"--- ERROR in reasoning_node calling Anthropic model: {type(e).__name__}: {e}")
                # --- End specific error logging ---
                # Handle errors gracefully
                return {
                    "messages": [
                        AIMessage(
                            content="I'm currently experiencing some rate limiting. Please try again in a moment."
                        )
                    ]
                }

        # Create the graph structure
        graph_builder = StateGraph(AgentState)
        
        # Add nodes to the graph
        graph_builder.add_node("reasoning_node", reasoning_node)  # AI reasoning
        graph_builder.add_node("tools", ToolNode(tools))          # Tool execution
        
        # Connect the nodes with edges to define the workflow
        graph_builder.add_edge(START, "reasoning_node")  # Start with reasoning
        
        # Conditionally route based on whether the model wants to use tools
        graph_builder.add_conditional_edges(
            "reasoning_node",           # From the reasoning node
            tools_condition,            # Check if tools are needed
            {"tools": "tools", END: END}  # If tools are needed, go to tools node, else end
        )
        
        # After tool execution, return to reasoning
        graph_builder.add_edge("tools", "reasoning_node")
        
        # Compile the graph to make it executable
        graph = graph_builder.compile()
        
        try:
            # Yield the compiled graph to the caller
            yield graph
        finally:
            # Clean up the MCP client when done
            # Note: Check if client has a close/cleanup method if needed
            if hasattr(client, 'close'):
                await client.close()
            elif hasattr(client, 'cleanup'):
                await client.cleanup() 