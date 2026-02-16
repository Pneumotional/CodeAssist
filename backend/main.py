import asyncio
import json
import os
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiosqlite
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from agent import CodeAssistAgent
from database import DatabaseManager

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")

try:
    from pydantic.warnings import PydanticDeprecatedSince20, PydanticDeprecatedSince211

    warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
    warnings.filterwarnings("ignore", category=PydanticDeprecatedSince211)
except Exception:
    pass

# ─── App Setup ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init()
    try:
        yield
    finally:
        await db.close()


app = FastAPI(title="CodeAssist Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

db = DatabaseManager()
security = HTTPBasic(auto_error=False)

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str

class LoginRequest(BaseModel):
    username: str
    api_key: str

class SessionCreate(BaseModel):
    name: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str
    api_key: str

# ─── Auth Helper ──────────────────────────────────────────────────────────────

async def verify_user(api_key: str) -> dict:
    user = await db.get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# ─── Auth Endpoints ───────────────────────────────────────────────────────────

@app.post("/auth/register")
async def register(req: RegisterRequest):
    """Register a new user and receive a unique API key."""
    existing = await db.get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    api_key = str(uuid.uuid4()).replace("-", "")
    user_id = await db.create_user(req.username, api_key)
    return {
        "user_id": user_id,
        "username": req.username,
        "api_key": api_key,
        "message": "Save your API key – it won't be shown again!",
    }

@app.post("/auth/login")
async def login(req: LoginRequest):
    """Login with username + API key."""
    user = await db.get_user_by_credentials(req.username, req.api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user_id": user["id"], "username": user["username"], "api_key": req.api_key}

# ─── Session Endpoints ────────────────────────────────────────────────────────

@app.get("/sessions")
async def list_sessions(api_key: str):
    user = await verify_user(api_key)
    sessions = await db.get_user_sessions(user["id"])
    return sessions

@app.post("/sessions")
async def create_session(req: SessionCreate, api_key: str):
    user = await verify_user(api_key)
    name = req.name or f"Session {datetime.now().strftime('%b %d %H:%M')}"
    session_id = await db.create_session(user["id"], name)
    return {"session_id": session_id, "name": name}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, api_key: str):
    user = await verify_user(api_key)
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete_session(session_id)
    # Clean up uploaded files for this session
    session_upload_dir = UPLOAD_DIR / session_id
    if session_upload_dir.exists():
        import shutil
        shutil.rmtree(session_upload_dir)
    return {"message": "Session deleted"}

@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, api_key: str):
    user = await verify_user(api_key)
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await db.get_session_messages(session_id)
    return messages

# ─── File Upload ──────────────────────────────────────────────────────────────

@app.post("/sessions/{session_id}/upload")
async def upload_file(session_id: str, api_key: str, file: UploadFile = File(...)):
    """Upload a file scoped to a specific session."""
    user = await verify_user(api_key)
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    session_upload_dir = UPLOAD_DIR / session_id
    session_upload_dir.mkdir(exist_ok=True)

    # Sanitize filename
    safe_name = Path(file.filename).name
    file_path = session_upload_dir / safe_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Store file reference in DB
    await db.add_session_file(session_id, safe_name, str(file_path))

    return {"filename": safe_name, "size": len(content), "message": "File uploaded successfully"}

@app.get("/sessions/{session_id}/files")
async def list_session_files(session_id: str, api_key: str):
    user = await verify_user(api_key)
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    files = await db.get_session_files(session_id)
    return files

@app.delete("/sessions/{session_id}/files/{filename}")
async def delete_file(session_id: str, filename: str, api_key: str):
    user = await verify_user(api_key)
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    file_path = UPLOAD_DIR / session_id / filename
    if file_path.exists():
        file_path.unlink()
    await db.remove_session_file(session_id, filename)
    return {"message": "File removed"}

# ─── Streaming Chat Endpoint ──────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream agent response via SSE."""
    user = await verify_user(req.api_key)
    session = await db.get_session(req.session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load session context: history + files
    history = await db.get_session_messages(req.session_id)
    files = await db.get_session_files(req.session_id)

    # Read file contents for context (session-scoped)
    file_context = ""
    for f in files:
        try:
            fp = Path(f["path"])
            if fp.exists() and fp.stat().st_size < 500_000:  # max 500KB
                file_context += f"\n\n--- File: {f['filename']} ---\n"
                file_context += fp.read_text(errors="replace")
        except Exception:
            pass

    # Save user message
    await db.add_message(req.session_id, "user", req.message)

    async def generate() -> AsyncGenerator[str, None]:
        full_response = ""
        try:
            agent = CodeAssistAgent()
            async for chunk in agent.stream_response(
                message=req.message,
                history=history,
                file_context=file_context,
                username=user["username"],
            ):
                full_response += chunk
                data = json.dumps({"type": "token", "content": chunk})
                yield f"data: {data}\n\n"

            # Save assistant response
            await db.add_message(req.session_id, "assistant", full_response)

            done_data = json.dumps({"type": "done", "content": full_response})
            yield f"data: {done_data}\n\n"

        except Exception as e:
            error_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL, "framework": "LlamaIndex + FastAPI"}
