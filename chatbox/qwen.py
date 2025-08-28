from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid
import os
from openai import OpenAI
from openai.types.chat import ChatCompletion

# --------------------
# Config
# --------------------
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise RuntimeError(
        "HF_TOKEN environment variable is not set. "
        "Get a Hugging Face access token and export HF_TOKEN=hf_xxx before starting the server."
    )

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN,
)

# --------------------
# App
# --------------------
app = FastAPI(title="Chatbot Backend (Qwen2.5-VL-7B-Instruct)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",   # your current dev origin
        "http://localhost:5500",   # handy alias
        "https://github.com/HoagnDawg35/UTEAILab-web-chatbot.io",
        "https://api.render.com/deploy/srv-d2k2i93e5dus738nj1jg?key=VOINrzC01a0"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# In-memory storage
# --------------------
# session_id -> list of {"role": "user"/"assistant", "content": "str"}
chat_sessions: Dict[str, List[Dict[str, str]]] = {}
# visitor_id -> list of visited pages
visit_log: Dict[str, List[str]] = {}

# --------------------
# Models
# --------------------
class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier returned by /api/new_session")
    message: str = Field(..., description="User message text")
    # Optional: URLs to images if you want to leverage the VL capability (must be HTTP/HTTPS).
    image_urls: Optional[List[str]] = Field(default=None, description="List of accessible image URLs")

class VisitLog(BaseModel):
    visitor_id: str
    page: str

# --------------------
# Helpers
# --------------------
MAX_HISTORY_MESSAGES = 30  # keep context bounded

def _trim_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # keep only the last N messages for safety
    return history[-MAX_HISTORY_MESSAGES:]

def _build_messages_for_api(
    history: List[Dict[str, str]],
    last_user_text: str,
    image_urls: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Build the OpenAI Chat Completions 'messages' payload.
    We keep your stored history as simple strings for compatibility with /api/history,
    but if image URLs are provided, we only modify the **last** user message for the API call.
    """
    # Copy history (shallow is enough since we only replace the last element when needed)
    to_send: List[Dict] = [dict(m) for m in history]

    if image_urls:
        # Make sure the last message is the one we just appended (user)
        if not to_send or to_send[-1]["role"] != "user":
            # Fallback: push a user message if something odd happens
            to_send.append({"role": "user", "content": last_user_text})

        content_parts = [{"type": "text", "text": last_user_text}]
        for url in image_urls:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise HTTPException(status_code=400, detail=f"image_urls must be HTTP/HTTPS: {url}")
            content_parts.append({"type": "image_url", "image_url": {"url": url}})

        to_send[-1] = {"role": "user", "content": content_parts}

    # Otherwise, just send as-is (plain text messages)
    return to_send

# --------------------
# Routes
# --------------------
@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_ID}

@app.get("/api/new_session")
def new_session():
    """Create a new chat session (used by frontend on first load)."""
    session_id = str(uuid.uuid4())
    chat_sessions[session_id] = []
    visit_log[session_id] = []  # also track visits per session
    return {"session_id": session_id}

@app.post("/api/chat")
def chat(req: ChatRequest):
    """Send a message to the chatbot and get a reply."""
    # Retrieve or initialize history
    history = chat_sessions.get(req.session_id)
    if history is None:
        # Create session on the fly if client forgot to call /api/new_session
        history = []
        chat_sessions[req.session_id] = history

    # Append user message (store only text for compatibility with /api/history)
    history.append({"role": "user", "content": req.message})
    chat_sessions[req.session_id] = _trim_history(history)

    # Build messages for the API (optionally include image URLs on just the last user turn)
    try:
        messages_payload = _build_messages_for_api(
            chat_sessions[req.session_id],
            last_user_text=req.message,
            image_urls=req.image_urls,
        )

        completion: ChatCompletion = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages_payload,
            temperature=0.7,
            max_tokens=1024,
            timeout=60,  # seconds
        )
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"Inference error: {str(e)}")

    reply = completion.choices[0].message.content or ""
    chat_sessions[req.session_id].append({"role": "assistant", "content": reply})

    return {"reply": reply}

@app.get("/api/history")
def get_history(session_id: str):
    """Return the chat history for a given session_id, mapped to {sender, text}."""
    if session_id not in chat_sessions:
        return {"messages": []}
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
