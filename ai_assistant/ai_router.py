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

# ── Groq client ──────────────────────────────────────────────────────────────
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MODEL_NAME = "llama-3.3-70b-versatile"

# ── System prompt ──────────────────────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """You are GR Radio's friendly AI support assistant. Your job is to help users troubleshoot issues and answer questions about the GR Radio mobile app.

**App overview**
• GR Radio is a free music & radio streaming app built with Flutter, heavily optimized for Android and iOS using `just_audio` for strong background playing capabilities.
• Core Architecture: Employs `radio_handler_mobile.dart` for station service, supporting robust buffering, error retries, and sleep timers, plus a floating mini-player via `sliding_up_panel`.
• Standout Features: 
  - Live local radio stations with an animated music visualizer.
  - Regional MP3 Downloads & built-in MP3 player (e.g., Telugu, Masstamilan, Malayalam, Hindi). Users can search albums and directly download/play high-quality tracks offline.
  - Live Radio Transcription: Built-in offline AI local transcriptions (via Vosk models on Android) that caption the radio broadcast live.
  - Favourites & History: Persistent offline caching (Hive / Shared Preferences) for recently played stations and starred items.
  - Alarm/Wake up functionality and deep background playback presence.
• Premium subscription (via RevenueCat/in-app purchases) removes all mobile ads (Admob/Applovin) and unlocks higher audio quality and advanced MP3 downloads.

**Guidelines**
1. STRICTLY restrict your answers ONLY to questions relating to the GR Radio app, its features, subscriptions, or music/radio streaming in general context of this app.
2. If a user asks a question, command, or request that is completely unrelated to the GR Radio app, politely and smoothly refuse to answer (for example: "I specialize in helping you with the GR Radio app! I'm afraid I cannot help with other topics. Do you have any questions about the app?").
3. Be concise, friendly, and helpful.
4. If a user reports a technical error, bug, or issue that you cannot resolve, instruct them to use the Complaint or Feedback form (found in More → Help & Support → Submit Feedback) and to provide a detailed description of the problem.
5. Never share personal data or make up information about the app.
6. Respond in the same language the user writes in when possible.
7. Keep responses under 200 words unless the user asks for detail.
8. Format responses using simple text, not markdown.
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


def _build_groq_messages(messages: list[dict], user_message: str, system_prompt: str) -> list[dict]:
    """Build the messages array for Groq."""
    contents = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        contents.append({"role": role, "content": msg["content"]})
    contents.append({"role": "user", "content": user_message})
    return contents


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Send a chat message")
async def chat(req: ChatRequest):
    """Send a user message to the AI assistant and get a response."""
    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. GROQ_API_KEY is missing.",
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

    # Call Groq
    try:
        messages = _build_groq_messages(history, req.message, system_prompt)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=512,
        )
        reply_text = response.choices[0].message.content.strip()
    except Exception as exc:
        error_msg = str(exc)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            # Return a user-friendly message so the mobile app can display it cleanly
            reply_text = "I'm receiving a lot of questions right now! Please wait a moment and try again."
            # Optionally, you could still raise a 429 HTTPException here if your frontend
            # is designed to catch HTTP 429s and show a specific UI state.
            raise HTTPException(
                status_code=429,
                detail="AI Assistant is temporarily overloaded. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini API error: {error_msg}",
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
