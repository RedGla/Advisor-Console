from fastapi import FastAPI, Depends, HTTPException, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, case
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
from llm_service import generate_llm_response, estimate_cost, conservative_token_estimate, MAX_COMPLETION_TOKENS, _select_grounding
import usage_service
import limits
import docs_service
import telemetry_service
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
    return {"id": c.id, "user_id": c.user_id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}

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
    today = usage_service._today_str()
    rows = (
        db.query(
            models.User,
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.messages_today), else_=0)), 0).label("messages_today"),
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.tokens_today), else_=0)), 0).label("tokens_today"),
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.est_spend_today), else_=0.0)), 0.0).label("est_spend_today"),
            func.coalesce(func.sum(models.UsageCounter.messages_today), 0).label("messages_all_time"),
            func.coalesce(func.sum(models.UsageCounter.tokens_today), 0).label("tokens_all_time"),
            func.coalesce(func.sum(models.UsageCounter.est_spend_today), 0.0).label("est_spend_all_time"),
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
            "messages_today": int(messages_today or 0),
            "tokens_today": int(tokens_today or 0),
            "est_spend_today": float(spend_today or 0.0),
            "messages_all_time": int(messages_all_time or 0),
            "tokens_all_time": int(tokens_all_time or 0),
            "est_spend_all_time": float(spend_all_time or 0.0),
            "last_usage_date": last_usage_date,
        }
        for user, messages_today, tokens_today, spend_today, messages_all_time, tokens_all_time, spend_all_time, last_usage_date in rows
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

@app.get("/admin/conversations/{conversation_id}/messages")
def get_admin_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    conversation = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [serialize_message(message) for message in conversation.messages]

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

def prepare_reserved_turn(db: Session, conv: models.Conversation, user_id: str, content: str):
    """Commit admission and both initial message rows together, or roll back all."""
    try:
        reservation = limits.reserve_daily_quota(db, user_id)
        history = [
            {"role": "user" if str(m.sender).lower() == "user" else "assistant",
             "content": m.content}
            for m in conv.messages
            if m.content and m.status == models.MessageStatus.COMPLETED.value
        ]
        history.append({"role": "user", "content": content})
        max_history = int(os.getenv("MAX_HISTORY_MESSAGES", "50"))
        if len(history) > max_history:
            history = history[-max_history:]

        user_msg = models.Message(conversation_id=conv.id, sender="user", content=content,
                                  status=models.MessageStatus.COMPLETED.value)
        db.add(user_msg)
        db.flush()
        assistant_msg = models.Message(conversation_id=conv.id, sender="assistant", content="",
                                       status=models.MessageStatus.PENDING.value)
        db.add(assistant_msg)
        if conv.title == "New Conversation":
            conv.title = content.strip().replace("\n", " ")[:60] or "New Conversation"
        db.flush()
        assistant_id = str(assistant_msg.id)
        db.commit()
        return reservation, assistant_id, history
    except BaseException:
        db.rollback()
        raise


def finish_reserved_turn(db: Session, reservation: usage_service.QuotaReservation,
                         assistant_id: str, *, result: dict | None = None,
                         release: bool = False,
                         token_reservation: usage_service.TokenReservation | None = None) -> dict:
    """Atomically reconcile/release quota and transition a pending assistant row.

    Locking the pending row makes retries of this finalization a no-op after
    the first committed transition. Provider/DB uncertainty retains the slot.
    """
    try:
        assistant = (db.query(models.Message).filter_by(id=assistant_id)
                     .populate_existing().with_for_update().one())
        if assistant.status == models.MessageStatus.PENDING.value:
            if result is not None:
                cost = estimate_cost(result["prompt_tokens"], result["completion_tokens"])
                usage_service.reconcile_reservation(
                    db, reservation, prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"], est_cost=cost,
                    token_reservation=token_reservation,
                    daily_cap=limits.MAX_TOKENS_PER_DAY,
                )
                assistant.content = result["content"]
                assistant.status = models.MessageStatus.COMPLETED.value
                assistant.prompt_tokens = result["prompt_tokens"]
                assistant.completion_tokens = result["completion_tokens"]
                assistant.est_cost = cost
            else:
                if release:
                    usage_service.release_reservation(db, reservation)
                    if token_reservation is not None:
                        usage_service.release_token_budget(db, reservation, token_reservation)
                assistant.content = "Sorry, I couldn't reach the advisor model right now. Please try again in a moment."
                assistant.status = models.MessageStatus.ERROR.value
        # Serialize before commit so no post-commit refresh opens a new transaction.
        response = serialize_message(assistant)
        db.commit()
        return response
    except BaseException:
        db.rollback()
        raise


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

    # Rate rejection must not create a counter or reserve a daily message slot.
    try:
        limits.check_rate_limit(user_id)
    except limits.RateLimitedError as exc:
        logger.warning("request_blocked reason=rate user_id=%s", user_id)
        telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id, status="blocked", reason="rate")
        retry_after = int(exc.retry_after_seconds)
        raise HTTPException(status_code=429, detail={
            "reason": "rate",
            "message": f"You're sending messages too quickly. Try again in {retry_after}s.",
            "retry_after_seconds": retry_after,
        })

    try:
        # All lock-waiting DB work runs off the event loop; no lock spans the LLM await.
        reservation, assistant_id, history = await run_in_threadpool(
            prepare_reserved_turn, db, conv, user_id, data.content,
        )
    except limits.CapExceededError:
        logger.warning("request_blocked reason=cap user_id=%s", user_id)
        telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id, status="blocked", reason="cap")
        raise HTTPException(status_code=429, detail={
            "reason": "cap",
            "message": "You've reached today's usage limit. Please try again tomorrow.",
        })
    logger.info("message_sent conversation_id=%s user_id=%s", conversation_id, user_id)
    telemetry_service.emit("message_sent", user_id=user_id, conversation_id=conversation_id,
                           status="accepted", user_input=data.content)

    token_reservation = None
    try:
        # Reserve a worst-case prompt envelope (including up to two 400-word
        # grounding chunks) before the provider call. This is deliberately
        # conservative so actual provider tokenization cannot exceed the cap.
        # Fetch the same cached context used by generation so the reservation
        # reflects the actual prompt envelope rather than a guessed constant.
        context = await docs_service.get_advisor_context(user_id=user_id, conversation_id=conversation_id)
        grounding = _select_grounding(context["grounding_document"], history[-1]["content"] if history else "")
        system_content = f"{context['system_prompt']}\n\n" + (f"Relevant grounding context:\n{grounding}" if grounding else "")
        prompt_estimate = conservative_token_estimate([{"role": "system", "content": system_content}, *history])
        try:
            token_reservation = await run_in_threadpool(
                usage_service.reserve_token_budget, db, reservation,
                prompt_tokens=prompt_estimate,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                daily_cap=limits.MAX_TOKENS_PER_DAY,
            )
        except ValueError:
            await run_in_threadpool(finish_reserved_turn, db, reservation, assistant_id, release=True)
            telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id,
                                   status="blocked", reason="cap")
            raise HTTPException(status_code=429, detail={
                "reason": "token_cap",
                "message": "You've reached today's token limit. Please try again tomorrow.",
            })
        try:
            result = await generate_llm_response(history, token_reservation.completion_tokens)
        except TypeError as exc:
            # Preserve compatibility with test doubles and legacy adapters
            # that still expose the single-argument callable.
            if "positional" not in str(exc) and "argument" not in str(exc):
                raise
            result = await generate_llm_response(history)
    except DatabaseOperationalError:
        # Unknown outcome: keep the reservation; the DB dependency returns 503.
        raise
    except HTTPException:
        raise
    except Exception as exc:
        pre_provider_failure = isinstance(exc, docs_service.DocsServiceError)
        event = "doc_fetch_error" if pre_provider_failure else "provider_error"
        logger.exception("%s conversation_id=%s", event, conversation_id)
        telemetry_service.emit(event, user_id=user_id, conversation_id=conversation_id,
                               status="error", reason=str(exc)[:500])
        await run_in_threadpool(
            finish_reserved_turn, db, reservation, assistant_id, release=pre_provider_failure,
            token_reservation=token_reservation,
        )
        raise HTTPException(status_code=502, detail="LLM generation failed")

    # A persistence failure after a successful provider call must not release quota
    # or be mistaken for a provider failure. Rollback leaves a pending reservation.
    response = await run_in_threadpool(
        finish_reserved_turn, db, reservation, assistant_id, result=result,
        token_reservation=token_reservation,
    )
    logger.info(
        "llm_call_completed conversation_id=%s user_id=%s prompt_tokens=%s "
        "completion_tokens=%s est_cost=%s docs_fetch_ms=%s llm_call_ms=%s",
        conversation_id, user_id, result["prompt_tokens"], result["completion_tokens"],
        response["est_cost"], result.get("docs_fetch_ms", 0), result.get("llm_call_ms", 0),
    )
    telemetry_service.emit("llm_call_completed", user_id=user_id, conversation_id=conversation_id,
                           status="completed", user_input=data.content,
                           assistant_response=response["content"],
                           prompt_tokens=result["prompt_tokens"],
                           completion_tokens=result["completion_tokens"],
                           estimated_cost=response["est_cost"])
    return response
