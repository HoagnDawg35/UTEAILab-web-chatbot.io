# # main.py
# import os
# import uuid
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from openai import OpenAI

# # Load Hugging Face token from environment variable
# HF_TOKEN = os.getenv("HF_TOKEN")

# # FastAPI app setup
# app = FastAPI()

# # CORS settings (update allow_origins for production)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://127.0.0.1:5500"],  # Change to your domain in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Hugging Face Inference Router client
# client = OpenAI(
#     base_url="https://router.huggingface.co/v1",
#     api_key=HF_TOKEN
# )

# # In-memory chat storage: {session_id: [{"role": "...", "content": "..."}]}
# chat_sessions = {}

# # Request schema
# class ChatRequest(BaseModel):
#     session_id: str
#     message: str

# @app.get("/api/new_session")
# def new_session():
#     """Generate a new unique session ID for each user."""
#     session_id = str(uuid.uuid4())
#     chat_sessions[session_id] = []  # Initialize empty history
#     return {"session_id": session_id}

# @app.post("/api/chat")
# def chat(req: ChatRequest):
#     """Handle chat messages for a given session."""
#     # Retrieve the session history
#     history = chat_sessions.get(req.session_id, [])
#     history.append({"role": "user", "content": req.message})

#     # Call LLaMA 3 model
#     completion = client.chat.completions.create(
#         model="meta-llama/Meta-Llama-3-8B-Instruct:novita",
#         messages=history
#     )

#     # Extract model reply
#     reply = completion.choices[0].message.content
#     history.append({"role": "assistant", "content": reply})

#     # Save updated history
#     chat_sessions[req.session_id] = history

#     return {
#         "reply": reply
#     }

# # Run using: uvicorn main:app --reload


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid, os
from openai import OpenAI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_TOKEN = os.getenv("HF_TOKEN")
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

# === In-memory storage ===
chat_sessions = {}  # session_id -> list of {"role": "user"/"assistant", "content": "..."}
visit_log = {}      # visitor_id -> list of visited pages

# === Request Models ===
class ChatRequest(BaseModel):
    session_id: str
    message: str

class VisitLog(BaseModel):
    visitor_id: str
    page: str


# ================= ROUTES =================

@app.get("/api/new_session")
def new_session():
    """Create a new chat session (used by frontend on first load)."""
    session_id = str(uuid.uuid4())
    chat_sessions[session_id] = []
    visit_log[session_id] = []  # ⚠️ Difference: also track visits per session
    return {"session_id": session_id}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Send a message to the chatbot and get a reply."""
    history = chat_sessions.get(req.session_id, [])
    history.append({"role": "user", "content": req.message})

    completion = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3-8B-Instruct:novita",
        # model = "Qwen/Qwen2.5-VL-3B-Instruct",
        messages=history
    )

    reply = completion.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    chat_sessions[req.session_id] = history

    return {"reply": reply}

@app.get("/api/history")
def get_history(session_id: str):
    """Return the chat history for a given session_id."""
    if session_id not in chat_sessions:
        return {"messages": []}  # ✅ safe fallback

    # ⚠️ Difference: map OpenAI-style {role, content} → frontend style {sender, text}
    mapped = [
        {"sender": "You" if msg["role"] == "user" else "AI", "text": msg["content"]}
        for msg in chat_sessions[session_id]
    ]
    return {"messages": mapped}


@app.post("/api/track_visit")
def track_visit(log: VisitLog):
    """Track which pages a visitor has seen."""
    if log.visitor_id not in visit_log:
        visit_log[log.visitor_id] = []
    visit_log[log.visitor_id].append(log.page)
    return {"status": "ok", "visitor_id": log.visitor_id, "pages": visit_log[log.visitor_id]}