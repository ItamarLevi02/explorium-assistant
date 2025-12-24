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
    # #region debug log
    import json
    with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"graph.py:38","message":"Before load_dotenv","data":{"env_file_exists":os.path.exists('.env'),"cwd":os.getcwd()},"timestamp":int(__import__('time').time()*1000)})+'\n')
    # #endregion
    load_dotenv()
    # #region debug log
    with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"graph.py:40","message":"After load_dotenv","data":{},"timestamp":int(__import__('time').time()*1000)})+'\n')
    # #endregion
    print("Starting to create LangGraph...")
    
    # Get API keys from environment
    explorium_api_key = os.getenv("EXPLORIUM_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    # #region debug log
    anthropic_key_stripped = anthropic_api_key.strip() if anthropic_api_key else None
    with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2,H3,H4","location":"graph.py:45","message":"API keys retrieved","data":{"explorium_key_exists":explorium_api_key is not None,"explorium_key_length":len(explorium_api_key) if explorium_api_key else 0,"anthropic_key_exists":anthropic_api_key is not None,"anthropic_key_length":len(anthropic_api_key) if anthropic_api_key else 0,"anthropic_key_has_whitespace":anthropic_api_key != anthropic_key_stripped if anthropic_api_key else False,"anthropic_key_prefix":anthropic_api_key[:10] if anthropic_api_key and len(anthropic_api_key) > 10 else None,"anthropic_key_suffix":anthropic_api_key[-10:] if anthropic_api_key and len(anthropic_api_key) > 10 else None},"timestamp":int(__import__('time').time()*1000)})+'\n')
    # #endregion
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
    # This uses a subprocess to run the MCP server locally
    async with MultiServerMCPClient({
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
    }) as client:
        print("MCP client initialized...")
        
        # Initialize the Claude language model with explicit API key
        # According to LangGraph documentation, passing api_key explicitly is recommended
        # #region debug log
        with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H4","location":"graph.py:88","message":"Before ChatAnthropic init","data":{"api_key_provided":anthropic_api_key is not None,"api_key_length":len(anthropic_api_key) if anthropic_api_key else 0},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        model = ChatAnthropic(
            model="claude-3-7-sonnet-20250219",
            temperature=0.7,
            api_key=anthropic_api_key
        )
        # #region debug log
        with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H4","location":"graph.py:92","message":"After ChatAnthropic init","data":{"model_created":model is not None},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        # Load all available tools from the MCP server
        tools = client.get_tools()
        print(f"Loaded {len(tools) if tools else 0} tools")
        
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
                # #region debug log
                with open('/Users/itamar.levi/Desktop/Projects/Project_1/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2,H4","location":"graph.py:131","message":"Error in reasoning_node","data":{"error_type":type(e).__name__,"error_message":str(e),"api_key_was_provided":anthropic_api_key is not None},"timestamp":int(__import__('time').time()*1000)})+'\n')
                # #endregion
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
        
        # Yield the compiled graph to the caller
        yield graph 