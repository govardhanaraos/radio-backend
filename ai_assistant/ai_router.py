"""
AI Assistant Router
───────────────────
Provides an in-app customer-support chatbot powered by Google Gemini (free tier).

MongoDB collections used:
  • ai_chat_sessions   – per-device message history
  • app_parameters     – config doc  config_key="ai_assistant"

Endpoints:
  POST   /ai/chat                      – send a user message, receive AI reply
  GET    /ai/chat/history/{device_id}  – fetch persisted chat history
  DELETE /ai/chat/history/{device_id}  – clear chat history
  GET    /ai/config                    – read AI-assistant feature flags
"""

import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from google import genai
from db.db import get_db

# ── Gemini client ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

MODEL_NAME = "gemini-2.0-flash"

# ── System prompt ──────────────────────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """You are GR Radio's friendly AI support assistant. Your job is to help users troubleshoot issues and answer questions about the GR Radio mobile app.

**App overview**
• GR Radio is a free music & radio streaming app available on Android and iOS.
• Features: live radio stations, MP3 player (local files), MP3 downloads, radio recording, favourites, recently played, dark mode, multilingual UI (English, Arabic, Telugu, Tamil, Kannada, Hindi).
• Premium subscription removes ads and unlocks higher audio quality.

**FAQ knowledge**
• How to use: Browse stations on the Discover screen, tap a station card to play. Use language chips or the search bar to filter.
• Audio buffering: Check internet connection; switch between Wi-Fi and mobile data.
• Report an issue: More → Help & Support → Submit Feedback.
• Offline listening: Live radio requires internet; premium users can download select content.
• Favourites: Tap the heart icon on any station tile; favourites appear at the top of Discover.
• Premium: Removes ads, higher quality, offline downloads. Available via More → Go Premium.

**Guidelines**
1. Be concise, friendly, and helpful.
2. If you cannot resolve an issue, suggest the user contact human support.
3. Never share personal data or make up information about the app.
4. Respond in the same language the user writes in when possible.
5. Keep responses under 200 words unless the user asks for detail.
6. Format responses using simple text, not markdown.
"""

# ── Router ─────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/ai", tags=["AI Assistant"])

COLLECTION = "ai_chat_sessions"
CONFIG_COLLECTION = "app_parameters"
CONFIG_KEY = "ai_assistant"


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    device_id: str
    message: str
    locale: str = "en"


class ChatResponse(BaseModel):
    reply: str
    timestamp: str


class ChatHistory(BaseModel):
    device_id: str
    messages: List[ChatMessage] = Field(default_factory=list)


class AiAssistantConfig(BaseModel):
    enabled: bool = True
    human_support_enabled: bool = True
    human_support_type: str = "email"           # email | whatsapp | url
    human_support_value: str = "support@grradio.app"
    human_support_label: str = "Email Support"
    max_history_messages: int = 50
    welcome_message: str = "Hi! I'm GR Radio's AI assistant. How can I help you today?"
    system_prompt_override: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_config() -> AiAssistantConfig:
    """Read AI assistant config from app_parameters collection."""
    db = get_db()
    if db is None:
        return AiAssistantConfig()
    doc = await db[CONFIG_COLLECTION].find_one(
        {"config_key": CONFIG_KEY}, {"_id": 0}
    )
    if not doc:
        return AiAssistantConfig()
    for key in ("config_key", "parameter_code"):
        doc.pop(key, None)
    try:
        return AiAssistantConfig(**doc)
    except Exception:
        return AiAssistantConfig()


async def _get_session(device_id: str) -> dict:
    """Get or create a chat session document."""
    db = get_db()
    session = await db[COLLECTION].find_one({"device_id": device_id})
    if session is None:
        session = {
            "device_id": device_id,
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db[COLLECTION].insert_one(session)
    return session


def _build_gemini_contents(messages: list[dict], user_message: str) -> list[dict]:
    """Build the contents array for Gemini, mapping our roles to Gemini roles."""
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Send a chat message")
async def chat(req: ChatRequest):
    """Send a user message to the AI assistant and get a response."""
    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. GEMINI_API_KEY is missing.",
        )

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")

    # Load config
    config = await _get_config()
    if not config.enabled:
        raise HTTPException(status_code=403, detail="AI assistant is currently disabled.")

    # Get or create session
    session = await _get_session(req.device_id)
    history = session.get("messages", [])

    # Trim history to max
    if len(history) > config.max_history_messages:
        history = history[-config.max_history_messages:]

    # Build system prompt
    system_prompt = config.system_prompt_override or DEFAULT_SYSTEM_PROMPT

    # Call Gemini
    try:
        contents = _build_gemini_contents(history, req.message)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=512,
            ),
        )
        reply_text = response.text.strip()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API error: {exc}",
        )

    # Save messages
    now = datetime.now(timezone.utc).isoformat()
    user_msg = {"role": "user", "content": req.message, "timestamp": now}
    assistant_msg = {"role": "assistant", "content": reply_text, "timestamp": now}

    await db[COLLECTION].update_one(
        {"device_id": req.device_id},
        {
            "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
            "$set": {"updated_at": now},
        },
    )

    return ChatResponse(reply=reply_text, timestamp=now)


@router.get(
    "/chat/history/{device_id}",
    response_model=ChatHistory,
    summary="Get chat history",
)
async def get_history(device_id: str):
    """Retrieve persisted chat history for a device."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")

    session = await db[COLLECTION].find_one(
        {"device_id": device_id}, {"_id": 0}
    )
    if not session:
        return ChatHistory(device_id=device_id, messages=[])

    config = await _get_config()
    messages = session.get("messages", [])
    # Return only the last N messages
    if len(messages) > config.max_history_messages:
        messages = messages[-config.max_history_messages:]

    return ChatHistory(device_id=device_id, messages=messages)


@router.delete(
    "/chat/history/{device_id}",
    summary="Clear chat history",
)
async def clear_history(device_id: str):
    """Clear all chat history for a device."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")

    await db[COLLECTION].update_one(
        {"device_id": device_id},
        {
            "$set": {
                "messages": [],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {"status": "ok", "message": "Chat history cleared."}


@router.get(
    "/config",
    response_model=AiAssistantConfig,
    summary="Get AI assistant configuration",
)
async def get_ai_config():
    """Return the AI assistant feature flags and human-support config."""
    return await _get_config()
