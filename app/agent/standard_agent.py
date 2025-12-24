import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

# The standard agent provides a direct comparison to the MCP agent
# It uses a single-step LLM call rather than a multi-step LangGraph workflow
# This file provides the streaming implementation for the "standard agent" panel

async def stream_standard_llm_response(user_input: str, websocket, manager):
    """
    Streams response from a standard ChatAnthropic LLM.
    
    This function represents the "standard agent" approach - a direct, single-step
    LLM call without the multi-step reasoning or external data enrichment that
    the MCP agent provides. It's used for side-by-side comparison.
    
    Args:
        user_input (str): The user's message/query
        websocket: The WebSocket connection to stream responses through
        manager: The ConnectionManager instance that handles message sending
        
    Processing Flow:
    1. Create LLM instance with streaming enabled
    2. Format the user input as a message
    3. Stream each chunk of the response to the frontend as it's generated
    4. Handle any errors that occur during generation
    """
    try:
        # Signal the frontend that the standard agent is starting to generate a response
        await manager.send_message(
            json.dumps({"type": "typing_start", "source": "standard"}),
            websocket
        )
        
        # Load environment variables
        load_dotenv()
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")
        
        # Create a ChatAnthropic instance using Claude
        # We use the same model family as the MCP agent for fair comparison
        # Note: Using haiku (lighter model) instead of sonnet (used by MCP agent)
        llm = ChatAnthropic(
            model='claude-3-haiku-20240307', 
            temperature=0.7, 
            streaming=True,
            api_key=anthropic_api_key
        )
        
        # Construct the formatted prompt content directly
        formatted_content = f"""
        You are a sales email assistant. Create a personalized sales email based 
        on the user's request. Research the company mentioned and draft a compelling 
        email that would be effective for sales outreach.
        
        User request: {user_input}
        
        Provide:
        1. Subject line
        2. Email body addressing potential decision-makers
        
        Make the email concise, persuasive, and personalized to the company's needs.
        **Keep the email body concise, aiming for approximately 3 short paragraphs.**
        """
        
        # Create the list of messages expected by the LLM
        messages_to_send = [HumanMessage(content=formatted_content)]
        
        # Pass the correctly formatted list of messages to astream
        async for chunk in llm.astream(messages_to_send):
            if chunk.content:
                # Format the chunk for the frontend, tagging it as coming from the standard agent
                message_to_send = {
                    "source": "standard",  # Identifies this as coming from the standard agent
                    "type": "ai",          # Message type for frontend rendering
                    "content": chunk.content
                }
                await manager.send_message(json.dumps(message_to_send), websocket)
                
    except Exception as e:
        # Handle any errors that occur during the streaming process
        error_content = f"Error in Standard Agent Stream: {type(e).__name__} - {str(e)}"
        try:
            # Send the error message to the frontend
            error_message = {
                "source": "standard", 
                "type": "error", 
                "content": error_content
            }
            await manager.send_message(json.dumps(error_message), websocket)
        except Exception as send_err:
            # If sending the error message fails, there's not much we can do
            # This could happen if the WebSocket connection is already closed
            pass
    
    finally:
        # Always signal completion, whether successful or due to an error
        try:
            # Tell the frontend that the standard agent has finished generating
            await manager.send_message(
                json.dumps({"type": "typing_end", "source": "standard"}),
                websocket
            )
            # Signal that processing is complete
            await manager.send_message(
                json.dumps({"type": "processing_complete", "source": "standard"}),
                websocket
            )
        except Exception:
            # Ignore errors in the completion message (WebSocket may be closed)
            pass 

async def send_standard_llm_response(user_input: str, websocket, manager):
    """
    Generates a complete response from a standard ChatAnthropic LLM and sends it.
    
    This function executes the standard agent logic in a single call and sends
    the final generated text via the provided WebSocket connection.
    
    Args:
        user_input (str): The user's message/query
        websocket: The WebSocket connection to send the response through.
        manager: The ConnectionManager instance to use for sending.
        
    Sends:
        A JSON message: {"type": "standard_final_email", "content": email_string}
        or {"type": "error", "source": "standard", "content": error_message}
    """
    final_content = ""
    try:
        # Load environment variables
        load_dotenv()
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")
        
        # Strip whitespace from API key if present
        anthropic_api_key = anthropic_api_key.strip()
        
        # Use the same model as the streaming version for consistency
        llm = ChatAnthropic(
            model='claude-3-haiku-20240307', 
            temperature=0.7, 
            streaming=False,
            api_key=anthropic_api_key
        ) # Ensure streaming=False
        
        # Construct the formatted prompt content directly
        # (Using the same prompt as the streaming version, including length constraint)
        formatted_content = f"""
        You are a sales email assistant. Create a personalized sales email based 
        on the user's request. Research the company mentioned and draft a compelling 
        email that would be effective for sales outreach.
        
        User request: {user_input}
        
        Provide:
        1. Subject line
        2. Email body addressing potential decision-makers
        
        Make the email concise, persuasive, and personalized to the company's needs.
        **Keep the email body concise, aiming for approximately 3 short paragraphs.**
        """
        
        # Create the list of messages expected by the LLM
        messages_to_send = [HumanMessage(content=formatted_content)]
        
        # Invoke the LLM to get the complete response
        response = await llm.ainvoke(messages_to_send)
        
        # Extract the content string
        final_content = response.content if response and response.content else "Standard agent produced no content."
        
        # Prepare and send the success message
        message_to_send = {
            "type": "standard_final_email", 
            "content": final_content
        }
        await manager.send_message(json.dumps(message_to_send), websocket)
                
    except Exception as e:
        # Log the error and prepare the error message
        error_content = f"Error in Standard Agent Generation: {type(e).__name__} - {str(e)}"
        print(error_content) # Log to server console
        # Prepare and send the error message
        message_to_send = {
            "type": "error",
            "source": "standard", # Indicate source for frontend handling
            "content": error_content
        }
        try:
            await manager.send_message(json.dumps(message_to_send), websocket)
        except Exception as send_err:
            print(f"Failed to send standard agent error to client: {send_err}")

# Keep the old streaming function for reference or potential future use, but it won't be called
async def stream_standard_llm_response(user_input: str, websocket, manager):
    # ... (original streaming code remains unchanged) ...
    pass # Ensure function exists if imported elsewhere, but does nothing if called

# --- Remove the old non-streaming function that returned a value ---
# async def get_standard_llm_response(user_input: str):
#    # ... (original code that returned value is removed) ...
#    pass

# Keep the old streaming function for reference or potential future use, but it won't be called
async def stream_standard_llm_response(user_input: str, websocket, manager):
    # ... (original streaming code remains unchanged) ...
    pass # Ensure function exists if imported elsewhere, but does nothing if called 