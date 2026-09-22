from fastapi import FastAPI, Depends, HTTPException, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr
from typing import Optional, cast, Literal
from datetime import datetime
import os
from dotenv import load_dotenv

from database import SessionLocal, DatabaseOperationalError
import models
import auth
from llm_service import generate_llm_response, estimate_cost
import usage_service
import limits
import docs_service
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
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


def get_db_or_503():
    """Like get_db, but converts SQLAlchemy OperationalErrors (connection drops,
    DB restarts, Supabase blips) into HTTP 503 with a user-friendly message
    instead of a raw 500 stack trace."""
    db = SessionLocal()
    try:
        yield db
    except DatabaseOperationalError:
        logger.exception("db_connection_error")
        raise HTTPException(
            status_code=503,
            detail="The database is temporarily unavailable. Please try again in a moment.",
        )
    finally:
        db.close()

# Auth Schemas
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str

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
    sender_role = "user" if sender and sender.lower() == "user" else "assistant"
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender": sender_role,
        "content": m.content,
        "status": m.status,
        "prompt_tokens": m.prompt_tokens,
        "completion_tokens": m.completion_tokens,
        "est_cost": m.est_cost,
        "created_at": created_at.isoformat() if created_at else None
    }

# Helper to get active user from session cookie
def get_current_user(request: Request, db: Session = Depends(get_db_or_503)):
    user_id = request.cookies.get("session_user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
    except DatabaseOperationalError:
        logger.exception("db_connection_error in get_current_user")
        raise HTTPException(
            status_code=503,
            detail="The database is temporarily unavailable. Please try again in a moment.",
        )
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
def register(data: RegisterSchema, db: Session = Depends(get_db_or_503)):
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
def login(data: LoginSchema, response: Response, db: Session = Depends(get_db_or_503)):
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

@app.post("/auth/change-password")
def change_password(data: ChangePasswordSchema, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_or_503)):
    if not auth.verify_password(data.current_password, cast(str, current_user.hashed_password)):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    current_user.hashed_password = auth.hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@app.get("/admin/usage")
def get_admin_usage(
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    rows = (
        db.query(
            models.User,
            func.coalesce(func.sum(models.UsageCounter.messages_today), 0).label("messages"),
            func.coalesce(func.sum(models.UsageCounter.tokens_today), 0).label("tokens"),
            func.coalesce(func.sum(models.UsageCounter.est_spend_today), 0.0).label("est_spend"),
            func.max(models.UsageCounter.date_str).label("last_usage_date"),
        )
        .outerjoin(models.UsageCounter, models.UsageCounter.user_id == models.User.id)
        .group_by(models.User.id)
        .order_by(models.User.created_at.desc())
        .all()
    )

    return [
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "messages": int(messages or 0),
            "tokens": int(tokens or 0),
            "est_spend": float(est_spend or 0.0),
            "last_usage_date": last_usage_date,
        }
        for user, messages, tokens, est_spend, last_usage_date in rows
    ]

@app.get("/admin/conversations")
def get_admin_conversations(
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    conversations = (
        db.query(models.Conversation, models.User.email)
        .join(models.User, models.User.id == models.Conversation.user_id)
        .order_by(models.Conversation.created_at.desc())
        .all()
    )
    return [
        {
            "id": conversation.id,
            "user_email": email,
            "title": conversation.title,
            "message_count": len(conversation.messages),
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        }
        for conversation, email in conversations
    ]

# Chat Endpoints
@app.post("/conversations")
def create_conversation(
    data: CreateConversationSchema,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(get_current_user)
):
    conv = models.Conversation(user_id=current_user.id, title=data.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return serialize_conversation(conv)

@app.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(get_current_user)
):
    convs = db.query(models.Conversation).filter(models.Conversation.user_id == current_user.id).all()
    return [serialize_conversation(c) for c in convs]

@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    data: RenameConversationSchema,
    db: Session = Depends(get_db_or_503),
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
    db: Session = Depends(get_db_or_503),
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
    db: Session = Depends(get_db_or_503),
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
    db: Session = Depends(get_db_or_503),
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
        # Run the FOR UPDATE cap check off the event loop so a waiting
        # concurrent request does not deadlock the worker.
        await run_in_threadpool(limits.check_daily_cap, db, user_id)
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
    history = [
        {
            "role": "user" if str(m.sender).lower() == "user" else "assistant",
            "content": m.content,
        }
        for m in conv.messages
        if m.content and m.status == models.MessageStatus.COMPLETED.value
    ]

    if conv.title == "New Conversation":
        conv.title = data.content.strip().replace("\n", " ")[:60] or "New Conversation"
        db.commit()

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
        result = await generate_llm_response(history)
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
    except DatabaseOperationalError:
        # DB dropped mid-LLM-call — can't persist the error row.  Return 503
        # so the client knows to retry rather than treating this as a bad
        # request (400) or an LLM failure (502).
        logger.exception("db_connection_error conversation_id=%s", conversation_id)
        raise HTTPException(
            status_code=503,
            detail="The database is temporarily unavailable. Please try again in a moment.",
        )
    except Exception as exc:
        # Plain-language fallback — never a raw stack trace to the client.
        if isinstance(exc, docs_service.DocsServiceError):
            logger.exception("doc_fetch_error conversation_id=%s", conversation_id)
        else:
            logger.exception("provider_error conversation_id=%s", conversation_id)
        setattr(
            assistant_msg,
            "content",
            "Sorry, I couldn't reach the advisor model right now. Please try again in a moment.",
        )
        setattr(assistant_msg, "status", models.MessageStatus.ERROR.value)
        db.commit()
        raise HTTPException(status_code=502, detail="LLM generation failed")

    db.commit()
    db.refresh(assistant_msg)
    return serialize_message(assistant_msg)