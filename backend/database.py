"""
Database manager using PostgreSQL with asyncpg.
"""
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection pool
_pool: Optional[asyncpg.Pool] = None

# Load configuration from environment variables
# Priority: Use DATABASE_URL if provided, otherwise construct from individual vars
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Parse DATABASE_URL to extract individual components
    # Format: postgresql://user:password@host:port/database
    import urllib.parse
    parsed = urllib.parse.urlparse(DATABASE_URL)
    
    DATABASE_CONFIG = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "database": parsed.path.lstrip("/") if parsed.path else "postgres",
        "min_size": int(os.getenv("DB_MIN_POOL_SIZE", "2")),
        "max_size": int(os.getenv("DB_MAX_POOL_SIZE", "10")),
    }
else:
    # Fallback to individual environment variables
    DATABASE_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "postgres"),
        "min_size": int(os.getenv("DB_MIN_POOL_SIZE", "2")),
        "max_size": int(os.getenv("DB_MAX_POOL_SIZE", "10")),
    }

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id       TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    api_key  TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content    TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS session_files (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    path       TEXT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    UNIQUE(session_id, filename)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_session_files_session_id ON session_files(session_id);
"""


class DatabaseManager:
    def __init__(self):
        global _pool
        self._pool = _pool

    async def init(self):
        """Initialize the database connection pool and create tables."""
        global _pool
        
        # Create connection pool
        _pool = await asyncpg.create_pool(**DATABASE_CONFIG)
        self._pool = _pool
        
        # Create tables
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        
        print("✅ PostgreSQL database initialized")

    async def close(self):
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            print("✅ PostgreSQL connection pool closed")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _now(self) -> datetime:
        """Return current UTC timestamp."""
        return datetime.utcnow()

    def _uid(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    async def _fetchone(self, sql: str, *params) -> Optional[Dict]:
        """Fetch a single row and convert to dict."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
            return dict(row) if row else None

    async def _fetchall(self, sql: str, *params) -> List[Dict]:
        """Fetch all rows and convert to list of dicts."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def _execute(self, sql: str, *params):
        """Execute a query without returning results."""
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *params)

    # ── Users ──────────────────────────────────────────────────────────────────

    async def create_user(self, username: str, api_key: str) -> str:
        """Create a new user."""
        uid = self._uid()
        await self._execute(
            "INSERT INTO users (id, username, api_key, created_at) VALUES ($1, $2, $3, $4)",
            uid, username, api_key, self._now()
        )
        return uid

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        return await self._fetchone("SELECT * FROM users WHERE username = $1", username)

    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict]:
        """Get user by API key."""
        return await self._fetchone("SELECT * FROM users WHERE api_key = $1", api_key)

    async def get_user_by_credentials(self, username: str, api_key: str) -> Optional[Dict]:
        """Get user by username and API key."""
        return await self._fetchone(
            "SELECT * FROM users WHERE username = $1 AND api_key = $2",
            username, api_key
        )

    # ── Sessions ───────────────────────────────────────────────────────────────

    async def create_session(self, user_id: str, name: str) -> str:
        """Create a new session."""
        sid = self._uid()
        now = self._now()
        await self._execute(
            "INSERT INTO sessions (id, user_id, name, created_at, updated_at) VALUES ($1, $2, $3, $4, $5)",
            sid, user_id, name, now, now
        )
        return sid

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        return await self._fetchone("SELECT * FROM sessions WHERE id = $1", session_id)

    async def get_user_sessions(self, user_id: str) -> List[Dict]:
        """Get all sessions for a user, ordered by most recent."""
        return await self._fetchall(
            "SELECT * FROM sessions WHERE user_id = $1 ORDER BY updated_at DESC",
            user_id
        )

    async def delete_session(self, session_id: str):
        """Delete a session (cascades to messages and files)."""
        await self._execute("DELETE FROM sessions WHERE id = $1", session_id)

    async def touch_session(self, session_id: str):
        """Update the session's updated_at timestamp."""
        await self._execute(
            "UPDATE sessions SET updated_at = $1 WHERE id = $2",
            self._now(), session_id
        )

    # ── Messages ───────────────────────────────────────────────────────────────

    async def add_message(self, session_id: str, role: str, content: str) -> str:
        """Add a message to a session."""
        mid = self._uid()
        await self._execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) VALUES ($1, $2, $3, $4, $5)",
            mid, session_id, role, content, self._now()
        )
        await self.touch_session(session_id)
        return mid

    async def get_session_messages(self, session_id: str) -> List[Dict]:
        """Get all messages for a session, ordered by creation time."""
        return await self._fetchall(
            "SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at ASC",
            session_id
        )

    # ── Session Files ──────────────────────────────────────────────────────────

    async def add_session_file(self, session_id: str, filename: str, path: str):
        """Add or update a file for a session."""
        fid = self._uid()
        async with self._pool.acquire() as conn:
            # Use INSERT ... ON CONFLICT for upsert
            await conn.execute(
                """INSERT INTO session_files (id, session_id, filename, path, uploaded_at)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (session_id, filename) 
                   DO UPDATE SET path = $4, uploaded_at = $5""",
                fid, session_id, filename, path, self._now()
            )

    async def get_session_files(self, session_id: str) -> List[Dict]:
        """Get all files for a session."""
        return await self._fetchall(
            "SELECT * FROM session_files WHERE session_id = $1 ORDER BY uploaded_at ASC",
            session_id
        )

    async def remove_session_file(self, session_id: str, filename: str):
        """Remove a file from a session."""
        await self._execute(
            "DELETE FROM session_files WHERE session_id = $1 AND filename = $2",
            session_id, filename
        )