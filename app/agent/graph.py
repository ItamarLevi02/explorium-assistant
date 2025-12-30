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

    # Try to find uv automatically if UV_PATH is not set or doesn't exist
    if not uv_path or not os.path.exists(uv_path):
        # Try common locations where uv might be installed
        import shutil
        uv_path = shutil.which("uv")  # Try to find uv in PATH
        if not uv_path:
            # Try common installation paths
            common_paths = [
                "/root/.cargo/bin/uv",  # Railway/Render after curl install
                "/usr/local/bin/uv",
                "/usr/bin/uv",
                os.path.expanduser("~/.cargo/bin/uv"),
            ]
            for path in common_paths:
                if os.path.exists(path):
                    uv_path = path
                    break
        
        if not uv_path:
            raise ValueError(
                "UV_PATH not found. Please either:\n"
                "1. Set UV_PATH environment variable to the path where uv is installed\n"
                "2. Install uv during build: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
                "3. Add uv to your PATH"
            )
        else:
            print(f"Found uv at: {uv_path}")

    # Try to auto-detect MCP_WORKING_DIR if not set or doesn't exist
    if not working_dir or not os.path.exists(working_dir):
        # Try common locations where mcp-explorium might be
        current_dir = os.getcwd()
        common_paths = [
            os.path.join(current_dir, "mcp-explorium"),  # Same directory as app
            os.path.join(current_dir, "..", "mcp-explorium"),  # Parent directory
            "/app/mcp-explorium",  # Railway default
            "/opt/render/project/src/mcp-explorium",  # Render default
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp-explorium"),  # Relative to this file
        ]
        
        for path in common_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                working_dir = abs_path
                print(f"Auto-detected MCP_WORKING_DIR: {working_dir}")
                break
        
        if not working_dir or not os.path.exists(working_dir):
            raise ValueError(
                f"MCP_WORKING_DIR not found. Tried: {common_paths}\n"
                "Please set MCP_WORKING_DIR environment variable to the path where mcp-explorium is located.\n"
                "In Railway, this should be: /app/mcp-explorium"
            )
    
    print(f"Using UV_PATH: {uv_path}")
    print(f"Using MCP_WORKING_DIR: {working_dir}")
    
    # Verify the MCP server file exists
    local_dev_server_path = os.path.join(working_dir, "local_dev_server.py")
    if not os.path.exists(local_dev_server_path):
        raise ValueError(
            f"MCP server file not found: {local_dev_server_path}\n"
            f"Please ensure mcp-explorium is in the correct location."
        )
    print(f"Verified MCP server file exists: {local_dev_server_path}")
    
    # Verify pyproject.toml exists (needed for uv)
    pyproject_path = os.path.join(working_dir, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        raise ValueError(
            f"pyproject.toml not found in {working_dir}\n"
            f"This is required for uv to install dependencies."
        )
    print(f"Verified pyproject.toml exists: {pyproject_path}")
    
    # --- End get paths ---
    
    # Initialize the MCP client that connects to the Explorium tool server
    # As of langchain-mcp-adapters 0.1.0, MultiServerMCPClient cannot be used as a context manager
    # Use the new API: create client and await get_tools()
    # According to the MCP server README, the correct command is:
    # uv run --directory <REPOSITORY_PATH> mcp run local_dev_server.py
    # Note: uv run should automatically install dependencies, but we ensure PATH includes uv
    import shutil
    # Ensure uv is in PATH for the subprocess
    env = os.environ.copy()
    env["EXPLORIUM_API_KEY"] = explorium_api_key
    # Add uv's directory to PATH if it's not already there
    uv_dir = os.path.dirname(uv_path)
    if uv_dir and uv_dir not in env.get("PATH", ""):
        env["PATH"] = f"{uv_dir}:{env.get('PATH', '')}"
    
    # Log the exact command that will be run for debugging
    cmd_str = f"{uv_path} run --directory {working_dir} mcp run local_dev_server.py"
    print(f"Will run MCP server with command: {cmd_str}")
    print(f"Environment PATH: {env.get('PATH', '')[:200]}...")  # First 200 chars
    print(f"EXPLORIUM_API_KEY set: {'Yes' if env.get('EXPLORIUM_API_KEY') else 'No'}")
    
    client = MultiServerMCPClient({
        "explorium": {
            "transport": "stdio",  # Communication via standard input/output
            "command": uv_path,    # Path to the UV package runner
            "args": [              # Arguments to run the local MCP server
                "run",
                "--directory",
                working_dir,       # Directory containing the MCP server
                "mcp",
                "run",
                "local_dev_server.py"  # Relative to the working directory
            ],
            "env": env,            # Environment variables including PATH
        }
    })
    print("MCP client initialized...")
    
    # Load all available tools from the MCP server (await is required in 0.1.0+)
    try:
        print(f"Attempting to load tools from MCP server at {working_dir}/local_dev_server.py...")
        tools = await client.get_tools()
        print(f"Loaded {len(tools) if tools else 0} tools")
        if tools:
            print(f"Tool names: {[tool.name for tool in tools[:5]]}...")  # Print first 5 tool names
    except Exception as e:
        print(f"ERROR loading tools from MCP server: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(
            f"Failed to load tools from MCP server: {e}\n"
            f"UV_PATH: {uv_path}\n"
            f"MCP_WORKING_DIR: {working_dir}\n"
            f"Please check that uv is installed and the MCP server path is correct."
        ) from e
    
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
        
        # Add a small delay to prevent rate limiting (only on first call)
        # Reduced delay to speed up processing
        if len(state.messages) <= 2:  # Only delay on initial calls
            await asyncio.sleep(0.5)  # Reduced from 2 seconds
        
        try:
            # Invoke the model with the current state
            response = cast(
                AIMessage,
                await bound_model.ainvoke(
                    [system_prompt, *state.messages],
                    config={
                        "max_retries": 2,
                        "timeout": 30,
                        "max_tokens": 4096,  # Reduce from default to prevent context overflow
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