from fastapi import FastAPI, Depends, HTTPException, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, cast, Literal
from datetime import datetime
import os
from dotenv import load_dotenv

from database import SessionLocal
import models
import auth
from llm_service import get_chat_completion, estimate_cost, LLMError
import usage_service
import limits
import logging

logger = logging.getLogger("advisor_console")

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configuration based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
IS_PROD = os.getenv("ENVIRONMENT", "development") == "production"

# Cookie configuration - can be overridden via env vars
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if IS_PROD else "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none" if IS_PROD else "lax")

# CORS configuration
ALLOWED_ORIGINS = [FRONTEND_URL]
if ENVIRONMENT == "development":
    # Allow additional local dev URLs in development
    ALLOWED_ORIGINS.extend(["http://localhost:3000", "http://127.0.0.1:5173"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth Schemas
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# Chat Schemas
class CreateConversationSchema(BaseModel):
    title: Optional[str] = "New Conversation"

class RenameConversationSchema(BaseModel):
    title: str

class SendMessageSchema(BaseModel):
    content: str

# Serializers
def serialize_conversation(c: models.Conversation) -> dict:
    return {"id": c.id, "user_id": c.user_id, "title": c.title, "created_at": c.created_at}

def serialize_message(m: models.Message) -> dict:
    """Serialize a Message object. Ensures 'sender' is always lowercase ('user' or 'assistant')."""
    sender = cast(Optional[str], m.sender)
    created_at = cast(Optional[datetime], m.created_at)
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender": sender.lower() if sender else "assistant",  # Normalize to lowercase
        "content": m.content,
        "status": m.status,
        "prompt_tokens": m.prompt_tokens,
        "completion_tokens": m.completion_tokens,
        "est_cost": m.est_cost,
        "created_at": created_at.isoformat() if created_at else None
    }

# Helper to get active user from session cookie
def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("session_user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

# Role Guard Dependency
def require_admin(current_user: models.User = Depends(get_current_user)):
    if cast(str, current_user.role) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}

@app.post("/auth/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing_user = auth.get_user_by_email(db, data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = auth.hash_password(data.password)
    new_user = models.User(email=data.email, hashed_password=hashed_pwd, role="user")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully", "user_id": new_user.id}

@app.post("/auth/login")
def login(data: LoginSchema, response: Response, db: Session = Depends(get_db)):
    user = auth.get_user_by_email(db, data.email)
    if not user or not auth.verify_password(
        data.password, cast(str, user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    response.set_cookie(
        key="session_user_id",
        value=str(user.id),
        httponly=True,
        samesite=cast(Literal["lax", "strict", "none"], COOKIE_SAMESITE),
        secure=COOKIE_SECURE,
    )
    return {"message": "Logged in successfully", "email": user.email, "role": user.role}

@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("session_user_id")
    return {"message": "Logged out successfully"}

@app.get("/auth/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role}

# Chat Endpoints
@app.post("/conversations")
def create_conversation(
    data: CreateConversationSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = models.Conversation(user_id=current_user.id, title=data.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return serialize_conversation(conv)

@app.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    convs = db.query(models.Conversation).filter(models.Conversation.user_id == current_user.id).all()
    return [serialize_conversation(c) for c in convs]

@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    data: RenameConversationSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty")

    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    setattr(conv, "title", title)
    db.commit()
    db.refresh(conv)
    return serialize_conversation(conv)

@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@app.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [serialize_message(m) for m in conv.messages]

@app.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: str,
    data: SendMessageSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_id = cast(str, current_user.id)

    # 0. Server-side caps + rate limit, enforced BEFORE anything is persisted
    #    or the LLM is called — the client cannot bypass these (FR-05/FR-06).
    try:
        limits.check_daily_cap(db, user_id)
    except limits.CapExceededError:
        logger.warning(f"request_blocked reason=cap user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "cap",
                "message": "You've reached today's usage limit. Please try again tomorrow.",
            },
        )

    try:
        limits.check_rate_limit(user_id)
    except limits.RateLimitedError as e:
        logger.warning(f"request_blocked reason=rate user_id={user_id}")
        retry_after = int(e.retry_after_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "rate",
                "message": f"You're sending messages too quickly. Try again in {retry_after}s.",
                "retry_after_seconds": retry_after,
            },
        )

    # 1. Save user message immediately so it's never lost even if the LLM call fails
    user_msg = models.Message(
        conversation_id=conversation_id,
        sender="user",
        content=data.content,
        status=models.MessageStatus.COMPLETED.value,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 2. Assemble the full conversation history for a real multi-turn call.
    #    Note: no system prompt is injected yet — the Google Docs persona/
    #    grounding pipeline (FR-02/FR-03) is a separate piece of work.
    history = [
        {"role": "user" if m.sender == "user" else "assistant", "content": m.content}
        for m in conv.messages
    ]

    # 3. Write the assistant row as "pending" BEFORE calling the LLM. This is
    #    what targets the "≥99% completed-turns-persisted" KPI: even if the
    #    process crashes mid-call, the turn already exists in the DB.
    assistant_msg = models.Message(
        conversation_id=conversation_id,
        sender="assistant",
        content="",
        status=models.MessageStatus.PENDING.value,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # 4. Call OpenRouter for a real reply, then update the pending row.
    try:
        result = await get_chat_completion(history)
        cost = estimate_cost(result["prompt_tokens"], result["completion_tokens"])

        setattr(assistant_msg, "content", result["content"])
        setattr(assistant_msg, "status", models.MessageStatus.COMPLETED.value)
        setattr(assistant_msg, "prompt_tokens", result["prompt_tokens"])
        setattr(assistant_msg, "completion_tokens", result["completion_tokens"])
        setattr(assistant_msg, "est_cost", cost)

        # Write-through into usage_counters (PRD §8) — what caps/admin view read from.
        usage_service.record_usage(
            db,
            user_id=user_id,
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            est_cost=cost,
        )
    except LLMError:
        # Plain-language fallback — never a raw stack trace to the client.
        # TODO(Day 10): also log a provider_error telemetry event once the
        # events table lands.
        setattr(
            assistant_msg,
            "content",
            "Sorry, I couldn't reach the advisor model right now. Please try again in a moment.",
        )
        setattr(assistant_msg, "status", models.MessageStatus.ERROR.value)

    db.commit()
    db.refresh(assistant_msg)
    return serialize_message(assistant_msg)