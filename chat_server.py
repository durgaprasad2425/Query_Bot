from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="Simple Chat API",
    description="A basic FastAPI server with a chat endpoint",
    version="1.0.0"
)

# Models for Request and Response
class Message(BaseModel):
    role: str # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []

class ChatResponse(BaseModel):
    reply: str
    status: str = "success"

@app.get("/")
async def root():
    return {"message": "Welcome to the Chat API. Use the /chat endpoint to start talking!"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint to handle chat messages.
    In a real application, you would integrate an LLM (like OpenAI, Gemini, or Claude) here.
    """
    try:
        user_input = request.message
        
        # Placeholder for LLM logic
        # Example: bot_reply = llm.generate(user_input, history=request.history)
        bot_reply = f"Echo: {user_input}. (This is a placeholder for your AI model logic.)"
        
        return ChatResponse(reply=bot_reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # To run the server, use: python chat_server.py
    # Or: uvicorn chat_server:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
