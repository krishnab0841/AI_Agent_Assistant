"""
Main FastAPI application for the AI Agent Assistant.
"""
import asyncio
import json
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import config

# Initialize FastAPI app
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION, 
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure the Gemini client
genai.configure(api_key=config.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """Register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_to_client(self, message: str, client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()

# --- Mock Tools (to be replaced with real APIs) ---
async def mock_schedule_meeting(person: str, date: str, time: str, subject: str):
    """Schedules a meeting on the user's calendar."""
    await asyncio.sleep(2)  # Simulate API call latency
    return json.dumps({
        "status": "success", 
        "details": f"Meeting with {person} about '{subject}' scheduled for {date} at {time}."
    })

async def mock_send_email(recipient: str, subject: str, body: str):
    """Sends an email to a specified recipient."""
    await asyncio.sleep(2)  # Simulate API call latency
    return json.dumps({
        "status": "success", 
        "message": f"Email with subject '{subject}' sent to {recipient}."
    })

# --- Specialized Agents ---
async def scheduler_agent(client_id: str, instruction: str):
    """Agent responsible for scheduling tasks by calling the calendar tool."""
    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": f"[Scheduler Agent] Task received: '{instruction}'"
        }), 
        client_id
    )
    result = await mock_schedule_meeting("John", "September 24, 2025", "2:00 PM", "Follow-up")
    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": f"[Scheduler Agent] Result: {json.loads(result)['details']}"
        }), 
        client_id
    )
    return "Scheduling complete."

async def email_agent(client_id: str, instruction: str):
    """Agent responsible for sending emails."""
    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": f"[Email Agent] Task received: '{instruction}'"
        }), 
        client_id
    )
    result = await mock_send_email("john@example.com", "Last Week's Summary", "Here is the summary you requested...")
    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": f"[Email Agent] Result: {json.loads(result)['message']}"
        }), 
        client_id
    )
    return "Email sent."

# --- Main Planner Agent ---
async def planner_agent(client_id: str, instruction: str):
    """The main agent that uses Gemini to create a plan and delegate tasks."""
    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": f"Planner received: '{instruction}'"
        }), 
        client_id
    )
    await asyncio.sleep(1)

    # Define the tools available to the planner agent
    tools = {
        "scheduler_agent": scheduler_agent,
        "email_agent": email_agent,
    }
    
    # This is the core Gemini Function Calling prompt
    prompt = f"""
    You are a helpful assistant. Based on the user's request, decide which agent should be called to handle the task.
    Today's date is September 23, 2025.
    User request: "{instruction}"
    """
    
    tool_config = {
        "function_declarations": [
            {
                "name": "scheduler_agent",
                "description": "Schedules a meeting, appointment, or event.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "instruction": {
                            "type": "STRING",
                            "description": "The user's full instruction related to scheduling. e.g., 'Schedule a meeting with John'"
                        }
                    },
                    "required": ["instruction"]
                }
            },
            {
                "name": "email_agent",
                "description": "Sends an email or a document.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "instruction": {
                            "type": "STRING",
                            "description": "The user's full instruction related to sending an email. e.g., 'send him last week's summary.'"
                        }
                    },
                    "required": ["instruction"]
                }
            }
        ]
    }

    try:
        # Gemini decides which tool to use
        response = model.generate_content(prompt, tools=tool_config)
        response_function_call = response.candidates[0].content.parts[0].function_call
        
        # Plan Execution
        if response_function_call:
            function_name = response_function_call.name
            function_args = response_function_call.args
            
            await manager.send_to_client(
                json.dumps({
                    "type": "tool_call", 
                    "message": f"Planner decided to use: {function_name}"
                }), 
                client_id
            )
            
            # Call the selected agent/function
            if function_name in tools:
                function_to_call = tools[function_name]
                task_instruction = function_args['instruction']
                await function_to_call(client_id, task_instruction)

            # This is a simplified example. For the user's request, a real agent would call scheduler, then email.
            # We will simulate the second call for demonstration.
            if "meeting" in instruction.lower() and "send" in instruction.lower():
                await manager.send_to_client(
                    json.dumps({
                        "type": "tool_call", 
                        "message": "Planner decided to use: email_agent"
                    }), 
                    client_id
                )
                await email_agent(client_id, "Send the summary to John")
        else:
            await manager.send_to_client(
                json.dumps({
                    "type": "log", 
                    "message": "I'm not sure how to handle that request."
                }), 
                client_id
            )

    except Exception as e:
        print(f"Error calling Gemini or executing tool: {e}")
        await manager.send_to_client(
            json.dumps({
                "type": "log", 
                "message": f"An error occurred: {e}"
            }), 
            client_id
        )

    await manager.send_to_client(
        json.dumps({
            "type": "log", 
            "message": "Planner finished."
        }), 
        client_id
    )

# --- API Endpoints ---
@app.post("/instruct/{client_id}")
async def handle_instruction(client_id: str, instruction: dict):
    """Handle a new instruction from a client."""
    user_input = instruction.get("message", "")
    if not user_input:
        return {"status": "error", "message": "Empty instruction"}
    
    asyncio.create_task(planner_agent(client_id, user_input))
    return {"status": "received", "client_id": client_id}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Handle WebSocket connections."""
    await manager.connect(client_id, websocket)
    print(f"Client #{client_id} connected.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client #{client_id} disconnected.")

# --- Main Entry Point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
