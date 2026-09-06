from fastapi import FastAPI, Depends, HTTPException, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, cast

from database import SessionLocal
import models
import auth

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    role: Optional[str] = "user"

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# Chat Schemas
class CreateConversationSchema(BaseModel):
    title: Optional[str] = "New Conversation"

class SendMessageSchema(BaseModel):
    content: str

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
def health_check():
    return {"status": "ok"}

@app.post("/auth/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing_user = auth.get_user_by_email(db, data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = auth.hash_password(data.password)
    new_user = models.User(email=data.email, hashed_password=hashed_pwd, role=data.role)
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
        samesite="lax",
        secure=False # Set to True in production HTTPS
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
    return conv

@app.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Conversation).filter(models.Conversation.user_id == current_user.id).all()

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
    return conv.messages

@app.post("/conversations/{conversation_id}/messages")
def post_message(
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

    # 1. Save user message
    user_msg = models.Message(
        conversation_id=conversation_id,
        sender="user",
        content=data.content
    )
    db.add(user_msg)
    
    # 2. Generate hardcoded echo stub reply
    stub_reply = f"Echo response: {data.content}"
    assistant_msg = models.Message(
        conversation_id=conversation_id,
        sender="assistant",
        content=stub_reply
    )
    db.add(assistant_msg)
    
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg