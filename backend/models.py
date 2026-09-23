import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from database import Base

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=UserRole.USER.value)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversations = relationship("Conversation", back_populates="user")
    usage_counters = relationship("UsageCounter", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Turn-completion tracking (targets the "≥99% completed-turns-persisted" KPI):
    # assistant rows are written as "pending" before the LLM call, then
    # updated to "completed" or "error" after. User rows are always "completed".
    status = Column(String, default=MessageStatus.COMPLETED.value, nullable=False)

    # Token/cost tracking — populated on assistant messages after a completed LLM call.
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    est_cost = Column(Float, default=0.0)

    conversation = relationship("Conversation", back_populates="messages")

class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "date_str", name="uq_usage_counters_user_day"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date_str = Column(String, nullable=False)  # e.g. "2026-09-14" — one row per user per day

    messages_today = Column(Integer, default=0)
    tokens_today = Column(Integer, default=0)
    reserved_tokens_today = Column(Integer, default=0, nullable=False)
    est_spend_today = Column(Float, default=0.0)

    user = relationship("User", back_populates="usage_counters")

class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    event = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True)
    user_input = Column(String, nullable=True)
    assistant_response = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
