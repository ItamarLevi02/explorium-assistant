import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from .agent.state import AgentState, EXPLORIUM_SYSTEM_PROMPT
from .agent.graph import create_explorium_langgraph
# Import the standard agent function that SENDS the message
from .agent.standard_agent import send_standard_llm_response
import uuid
from dotenv import load_dotenv
import re # Import regex module

# Load environment variables from .env file
# This ensures API keys and configuration are properly loaded
load_dotenv()

# Initialize the FastAPI application
app = FastAPI()

# Mount the static files directory to serve frontend assets (HTML, CSS, JS)
# This makes files in app/static available at the /static URL path
app.mount("/static", StaticFiles(directory="app/static"), name="static")

class ConnectionManager:
    """
    Manages WebSocket connections and message delivery.
    Responsible for tracking active connections and sending messages to clients.
    """
    def __init__(self):
        # List to track all active WebSocket connections
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection and add it to the active connections list.
        
        Args:
            websocket: The WebSocket connection to accept
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from the active connections list.
        Called when a client disconnects.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        """
        Send a text message to a specific WebSocket client.
        
        Args:
            message: The message to send (typically JSON-serialized)
            websocket: The WebSocket connection to send to
        """
        await websocket.send_text(message)

# Create an instance of the connection manager
manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get():
    """
    Root endpoint handler - serves the main HTML file.
    When users visit the site, this returns the frontend interface.
    
    Returns:
        The contents of index.html
    """
    try:
        with open("app/static/index.html") as f:
            return f.read()
    except Exception as e:
        print(f"Error serving index.html: {e}")
        return HTMLResponse(content=f"<h1>Error loading page</h1><p>{str(e)}</p>", status_code=500)

@app.get("/health")
async def health():
    """Health check endpoint to verify the app is running."""
    return {"status": "ok", "message": "Application is running"}

# --- Define Helper Coroutine for MCP that SENDS final email AND intermediate steps ---
async def run_mcp_and_send_final(state: AgentState, graph_instance, websocket, manager):
    """
    Runs the MCP graph using streaming, attempts to parse structured email components
    from the final AI message, sends the structured email, and then sends collected
    intermediate steps.

    Args:
        state: The current agent state.
        graph_instance: The compiled LangGraph instance.
        websocket: The WebSocket connection for sending messages.
        manager: The ConnectionManager instance.

    Sends:
        - {"type": "mcp_final_email", "content": structured_email_dict} if successful
        - {"type": "error", "source": "mcp", "content": ...} if parsing fails or error occurs
        - {"type": "mcp_intermediate_steps", "steps": [...] } containing collected steps
    """
    structured_email_data = None # Will store the dict {"potential_contacts", "subject", "body"}
    intermediate_steps = []
    last_ai_message_content = None

    try:
        print("--- [MCP Helper] Starting graph stream...")
        async for event in graph_instance.astream(
            state,
            config={"recursion_limit": 50}, # Increase recursion limit
            stream_mode="values"
        ):
            # --- Collect Intermediate Steps ---
            # Heuristic: Capture tool calls/results and AI messages before the final one
            # Note: Event structure might vary, adjust keys as needed based on actual LangGraph output
            if isinstance(event, dict):
                if "messages" in event:
                    latest_msg = event["messages"][-1]
                    if isinstance(latest_msg, AIMessage):
                        last_ai_message_content = latest_msg.content
                        if latest_msg.tool_calls:
                            for tc in latest_msg.tool_calls:
                                intermediate_steps.append({
                                    "step_type": "ai_tool_call",
                                    "tool_name": tc.get('name'),
                                    "tool_args": tc.get('args')
                                })
                        else: # Assume thinking step
                             intermediate_steps.append({
                                 "step_type": "ai_thought",
                                 "content": last_ai_message_content
                             })
                    elif isinstance(latest_msg, ToolMessage):
                        intermediate_steps.append({
                            "step_type": "tool_result",
                            "tool_name": latest_msg.name,
                            "content": latest_msg.content
                        })
            # --- End Collect Intermediate Steps ---

        print("--- [MCP Helper] Graph stream finished.")

        # --- Process Final Message ---
        if last_ai_message_content:
            extracted_text = ""
            if isinstance(last_ai_message_content, str):
                extracted_text = last_ai_message_content
            elif isinstance(last_ai_message_content, list) and len(last_ai_message_content) > 0 and isinstance(last_ai_message_content[0], dict) and last_ai_message_content[0].get('type') == 'text':
                extracted_text = last_ai_message_content[0].get('text', '')
            extracted_text = extracted_text.strip()

            if extracted_text:
                print(f"--- [MCP Helper] Attempting to parse final AI message text: '{extracted_text[:100]}...'" )
                # --- >>> Attempt to parse structured email using Regex <<< ---
                try:
                    # Regex patterns (adjust if format changes)
                    # Making subject optional in matching to handle cases where it might be missing
                    contacts_match = re.search(r"Potential Contacts:(.*?)(Subject:|Body:|$)", extracted_text, re.DOTALL | re.IGNORECASE)
                    subject_match = re.search(r"Subject:(.*?)(Body:|$)", extracted_text, re.DOTALL | re.IGNORECASE)
                    body_match = re.search(r"Body:(.*)", extracted_text, re.DOTALL | re.IGNORECASE)

                    if body_match: # Body is mandatory
                        structured_email_data = {
                            "potential_contacts": contacts_match.group(1).strip() if contacts_match else "",
                            "subject": subject_match.group(1).strip() if subject_match else "",
                            "body": body_match.group(1).strip() # Keep <<<mcp_data>>> tags here
                        }
                        print("--- [MCP Helper] Successfully parsed structured email data.")
                    else:
                        print("--- [MCP Helper] Failed to find 'Body:' marker in final AI message.")

                except Exception as parse_err:
                     print(f"--- [MCP Helper] Error parsing final AI message text with regex: {parse_err}")
                # --- >>> End parsing <<< ---
            else:
                print("--- [MCP Helper] Final AI message content was empty.")
        else:
             print("--- [MCP Helper] No AI message content recorded as last.")

        # --- Send Final Structured Email (or error) ---
        if structured_email_data:
            message_to_send = {"type": "mcp_final_email", "content": structured_email_data} # Send dict
            await manager.send_message(json.dumps(message_to_send), websocket)
            print("--- [MCP Helper] Sent mcp_final_email with structured data.")
        else:
            # Send error if parsing failed or draft wasn't identified
            error_detail = "Could not parse structured email from final AI message." if extracted_text else "MCP agent did not produce a final email draft text."
            print(f"--- [MCP Helper] Failed to get structured email data. Reason: {error_detail}")
            error_message = {"type": "error", "source": "mcp", "content": error_detail}
            await manager.send_message(json.dumps(error_message), websocket)

        # --- Send Intermediate Steps ---
        if intermediate_steps:
             if intermediate_steps[-1].get("step_type") == "ai_thought" and intermediate_steps[-1].get("content") == last_ai_message_content:
                 intermediate_steps.pop()

             steps_message = {"type": "mcp_intermediate_steps", "steps": intermediate_steps}
             await manager.send_message(json.dumps(steps_message), websocket)
             print(f"--- [MCP Helper] Sent mcp_intermediate_steps ({len(intermediate_steps)} steps).")
        else:
             print("--- [MCP Helper] No intermediate steps collected.")

    except Exception as invoke_err:
        error_content = f"Error during MCP graph streaming: {invoke_err}"
        print(f"--- [MCP Helper] {error_content}")
        error_message = {"type": "error", "source": "mcp", "content": error_content}
        try:
            await manager.send_message(json.dumps(error_message), websocket)
        except Exception as send_err:
             print(f"Failed to send MCP agent error to client: {send_err}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint handler - NEW WORKFLOW: runs agents silently, sends final results.
    """
    await manager.connect(websocket)
    print("--- WebSocket connected --- ") # Log connection
    graph = None 
    try:
        # Create the graph instance using the async context manager
        print("--- Attempting to create graph context ---")
        async with create_explorium_langgraph({}) as graph_instance:
            graph = graph_instance 
            print("--- Graph context created successfully --- ") # Log graph success

            # Loop to handle incoming messages from the client
            while True:
                data = await websocket.receive_text()
                print(f"--- [Backend Received] Raw Data: {data}") # Log raw data received
                
                try:
                    message_data = json.loads(data)
                    user_input = message_data.get("message")
                    print(f"--- [Backend Received] Parsed User Input: {user_input}") # Log parsed input
                except json.JSONDecodeError:
                    print("--- [Backend Error] Failed to parse incoming JSON data.")
                    continue # Skip if message is not valid JSON
                except Exception as parse_err:
                    print(f"--- [Backend Error] Error processing received data: {parse_err}")
                    continue

                if not user_input:
                    print("--- [Backend Received] Empty user input, waiting for next message.")
                    continue

                # Prepare the initial state for the LangGraph agent
                print("--- Preparing agent state ---") 
                state = AgentState(messages=[HumanMessage(content=user_input)])
                print("--- Agent state prepared --- ")

                # --- Agent Processing Block --- 
                # Start tasks, they will send messages independently
                try:
                    print("--- >>> Entering Agent Processing Block <<< ---") # Log entry to processing block
                    print("--- Starting Background Agent Tasks (No Gather) --- ") # Log before dispatching tasks
                    # Create tasks but don't await results here
                    asyncio.create_task(run_mcp_and_send_final(state, graph, websocket, manager))
                    asyncio.create_task(send_standard_llm_response(user_input, websocket, manager))
                    print("--- Background Agent Tasks Dispatched --- ") # Log after dispatching tasks
                    
                except Exception as e:
                    # Handle errors during task creation/dispatching (less likely)
                    error_content = f"Error dispatching background tasks: {str(e)}"
                    print(error_content)
                    try:
                        await manager.send_message(
                            json.dumps({"type": "error", "source": "system", "content": error_content}),
                            websocket
                        )
                    except Exception as send_err:
                        pass
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("--- WebSocket disconnected --- ") # Log disconnect
    except Exception as e:
        # Handle broader connection/setup errors
        print(f"--- WebSocket Error (Outer Level): {e}") # Log outer errors
        # Ensure disconnection on outer errors as well
        if websocket in manager.active_connections:
            manager.disconnect(websocket)
    finally:
        # Final cleanup log
        print("--- Exiting websocket_endpoint --- ")
        if websocket in manager.active_connections:
            # This might be redundant if already disconnected, but safe
            manager.disconnect(websocket)

# Server startup code - only runs if this file is executed directly
if __name__ == "__main__":
    import uvicorn
    # Start the FastAPI server with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 